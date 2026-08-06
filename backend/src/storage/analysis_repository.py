from __future__ import annotations

from dataclasses import asdict
from typing import Iterable

from src.domain.models.detection import (
    Detection,
    IdentityCluster,
    JerseyVote,
    Tracklet,
    TrackletCrop,
    TrackletEmbedding,
)
from src.storage.db import Database


class AnalysisRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def bulk_insert_detections(self, detections: Iterable[Detection]) -> None:
        values = [
            (
                item.source_id,
                item.tracklet_id,
                item.ts,
                item.x,
                item.y,
                item.w,
                item.h,
                item.conf,
            )
            for item in detections
        ]
        if not values:
            return
        with self.database.connect() as connection:
            connection.executemany(
                """
                INSERT INTO detections(source_id, tracklet_id, ts, x, y, w, h, conf)
                SELECT ?, ?, ?, ?, ?, ?, ?, ?
                WHERE NOT EXISTS (
                    SELECT 1 FROM detections
                    WHERE source_id = ? AND tracklet_id IS ? AND ts = ?
                      AND x = ? AND y = ? AND w = ? AND h = ?
                )
                """,
                [value + value[:7] for value in values],
            )

    def detections_in_range(
        self, source_id: str, start_ts: float, end_ts: float
    ) -> list[Detection]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM detections
                WHERE source_id = ? AND ts BETWEEN ? AND ?
                ORDER BY ts, detection_id
                """,
                (source_id, start_ts, end_ts),
            ).fetchall()
        return [Detection(**dict(row)) for row in rows]

    def detections_near(
        self, source_id: str, ts: float, window_s: float = 0.5
    ) -> list[Detection]:
        rows = self.detections_in_range(source_id, ts - window_s, ts + window_s)
        if not rows:
            return []
        nearest_ts = min({row.ts for row in rows}, key=lambda value: abs(value - ts))
        return [row for row in rows if row.ts == nearest_ts]

    def max_detection_ts(self, source_id: str) -> float | None:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT MAX(ts) AS ts FROM detections WHERE source_id = ?", (source_id,)
            ).fetchone()
        return row["ts"] if row else None

    def bulk_upsert_tracklets(self, tracklets: Iterable[Tracklet]) -> None:
        values = [
            (
                item.tracklet_id,
                item.source_id,
                item.start_ts,
                item.end_ts,
                item.frame_count,
                item.avg_conf,
                item.kit_color_name,
                item.kit_color_hsv,
                item.cluster_id,
                item.cluster_assignment,
                int(item.synthetic),
            )
            for item in tracklets
        ]
        if not values:
            return
        with self.database.connect() as connection:
            connection.executemany(
                """
                INSERT INTO tracklets VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(tracklet_id) DO UPDATE SET
                    start_ts = MIN(tracklets.start_ts, excluded.start_ts),
                    end_ts = MAX(tracklets.end_ts, excluded.end_ts),
                    frame_count = excluded.frame_count,
                    avg_conf = excluded.avg_conf,
                    kit_color_name = excluded.kit_color_name,
                    kit_color_hsv = excluded.kit_color_hsv,
                    cluster_id = excluded.cluster_id,
                    cluster_assignment = excluded.cluster_assignment,
                    synthetic = excluded.synthetic
                """,
                values,
            )

    def get_tracklet(self, tracklet_id: str) -> Tracklet:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM tracklets WHERE tracklet_id = ?", (tracklet_id,)
            ).fetchone()
        if row is None:
            raise KeyError(tracklet_id)
        payload = dict(row)
        payload["synthetic"] = bool(payload["synthetic"])
        return Tracklet(**payload)

    def list_tracklets(self, source_id: str) -> list[Tracklet]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM tracklets WHERE source_id = ? ORDER BY start_ts",
                (source_id,),
            ).fetchall()
        return [Tracklet(**{**dict(row), "synthetic": bool(row["synthetic"])}) for row in rows]

    def repair_discontinuous_tracklets(
        self,
        source_id: str,
        project_id: str,
        *,
        max_gap_s: float = 1.0,
    ) -> int:
        with self.database.transaction(immediate=True) as connection:
            connection.execute("DROP TABLE IF EXISTS temp.continuity_detection_map")
            connection.execute("DROP TABLE IF EXISTS temp.continuity_segments")
            connection.execute(
                """
                CREATE TEMP TABLE continuity_detection_map AS
                WITH ordered AS (
                    SELECT d.detection_id, d.tracklet_id AS old_id, d.ts,
                        CASE WHEN d.ts - LAG(d.ts) OVER (
                            PARTITION BY d.tracklet_id
                            ORDER BY d.ts, d.detection_id
                        ) > ? THEN 1 ELSE 0 END AS starts_segment
                    FROM detections d
                    JOIN tracklets t ON t.tracklet_id = d.tracklet_id
                    WHERE d.source_id = ? AND d.tracklet_id IS NOT NULL
                      AND t.synthetic = 0
                )
                SELECT detection_id, old_id, ts,
                    SUM(starts_segment) OVER (
                        PARTITION BY old_id ORDER BY ts, detection_id
                        ROWS UNBOUNDED PRECEDING
                    ) AS segment_number
                FROM ordered
                """,
                (max_gap_s, source_id),
            )
            connection.execute(
                "CREATE UNIQUE INDEX continuity_detection_id_idx "
                "ON continuity_detection_map(detection_id)"
            )
            connection.execute(
                "CREATE INDEX continuity_detection_segment_idx "
                "ON continuity_detection_map(old_id, segment_number)"
            )
            connection.execute(
                """
                CREATE TEMP TABLE continuity_segments AS
                SELECT m.old_id, m.segment_number,
                    m.old_id || '-resume-' || printf('%010d', ROUND(MIN(m.ts) * 1000))
                        AS new_id,
                    MIN(m.ts) AS start_ts,
                    MAX(m.ts) AS end_ts,
                    COUNT(*) AS frame_count,
                    AVG(d.conf) AS avg_conf
                FROM continuity_detection_map m
                JOIN detections d ON d.detection_id = m.detection_id
                GROUP BY m.old_id, m.segment_number
                """
            )
            connection.execute(
                "CREATE UNIQUE INDEX continuity_segment_id_idx "
                "ON continuity_segments(old_id, segment_number)"
            )
            connection.execute(
                "CREATE INDEX continuity_segment_time_idx "
                "ON continuity_segments(old_id, start_ts, end_ts)"
            )
            connection.execute(
                """
                DELETE FROM continuity_segments
                WHERE old_id IN (
                    SELECT old_id FROM continuity_segments
                    GROUP BY old_id HAVING COUNT(*) = 1
                )
                """
            )
            replacement_count = int(
                connection.execute(
                    "SELECT COUNT(*) FROM continuity_segments"
                ).fetchone()[0]
            )
            if replacement_count == 0:
                return 0

            orphaned_crops = int(
                connection.execute(
                    """
                    SELECT COUNT(*) FROM tracklet_crops c
                    WHERE c.tracklet_id IN (
                        SELECT DISTINCT old_id FROM continuity_segments
                    ) AND NOT EXISTS (
                        SELECT 1 FROM continuity_segments s
                        WHERE s.old_id = c.tracklet_id
                          AND c.ts BETWEEN s.start_ts - 0.000001
                                       AND s.end_ts + 0.000001
                    )
                    """
                ).fetchone()[0]
            )
            if orphaned_crops:
                raise RuntimeError(
                    f"Cannot repair track continuity: {orphaned_crops} crops have no segment"
                )

            connection.execute(
                """
                INSERT INTO tracklets(
                    tracklet_id, source_id, start_ts, end_ts, frame_count,
                    avg_conf, kit_color_name, kit_color_hsv, cluster_id,
                    cluster_assignment, synthetic
                )
                SELECT s.new_id, ?, s.start_ts, s.end_ts, s.frame_count,
                    s.avg_conf, NULL, NULL, NULL,
                    COALESCE(t.cluster_assignment, 'auto'), t.synthetic
                FROM continuity_segments s
                JOIN tracklets t ON t.tracklet_id = s.old_id
                """,
                (source_id,),
            )
            connection.execute(
                """
                UPDATE detections AS d SET tracklet_id = (
                    SELECT s.new_id
                    FROM continuity_detection_map m
                    JOIN continuity_segments s
                      ON s.old_id = m.old_id
                     AND s.segment_number = m.segment_number
                    WHERE m.detection_id = d.detection_id
                )
                WHERE d.source_id = ? AND d.tracklet_id IN (
                    SELECT DISTINCT old_id FROM continuity_segments
                )
                """,
                (source_id,),
            )
            connection.execute(
                """
                UPDATE tracklet_crops AS c SET tracklet_id = (
                    SELECT s.new_id FROM continuity_segments s
                    WHERE s.old_id = c.tracklet_id
                      AND c.ts BETWEEN s.start_ts - 0.000001
                                   AND s.end_ts + 0.000001
                    LIMIT 1
                )
                WHERE c.tracklet_id IN (
                    SELECT DISTINCT old_id FROM continuity_segments
                )
                """
            )

            click_rows = connection.execute(
                """
                SELECT click_id, ts, resolved_tracklet_id
                FROM user_clicks
                WHERE project_id = ? AND resolved_tracklet_id IN (
                    SELECT DISTINCT old_id FROM continuity_segments
                )
                """,
                (project_id,),
            ).fetchall()
            segment_rows = connection.execute(
                "SELECT old_id, new_id, start_ts, end_ts FROM continuity_segments"
            ).fetchall()
            segments_by_old: dict[str, list[object]] = {}
            for segment in segment_rows:
                segments_by_old.setdefault(segment["old_id"], []).append(segment)
            for click in click_rows:
                timestamp = float(click["ts"])
                selected = min(
                    segments_by_old[click["resolved_tracklet_id"]],
                    key=lambda segment: (
                        0
                        if float(segment["start_ts"]) - 0.5
                        <= timestamp
                        <= float(segment["end_ts"]) + 0.5
                        else min(
                            abs(timestamp - float(segment["start_ts"])),
                            abs(timestamp - float(segment["end_ts"])),
                        ),
                        float(segment["start_ts"]),
                    ),
                )
                connection.execute(
                    "UPDATE user_clicks SET resolved_tracklet_id = ? WHERE click_id = ?",
                    (selected["new_id"], click["click_id"]),
                )

            connection.execute(
                "DELETE FROM jersey_votes WHERE tracklet_id IN "
                "(SELECT tracklet_id FROM tracklets WHERE source_id = ?)",
                (source_id,),
            )
            connection.execute(
                "UPDATE tracklets SET cluster_id = NULL WHERE source_id = ?",
                (source_id,),
            )
            connection.execute(
                "DELETE FROM identity_clusters WHERE source_id = ?",
                (source_id,),
            )
            connection.execute(
                "DELETE FROM appearance_segments WHERE project_id = ?",
                (project_id,),
            )
            connection.execute(
                "UPDATE projects SET target_cluster_id = NULL, status = 'analyzing' "
                "WHERE project_id = ?",
                (project_id,),
            )
            connection.execute(
                """
                DELETE FROM tracklets WHERE tracklet_id IN (
                    SELECT DISTINCT old_id FROM continuity_segments
                )
                """
            )
            return replacement_count

    def bulk_insert_crops(self, crops: Iterable[TrackletCrop]) -> None:
        self._bulk_upsert("tracklet_crops", crops, "crop_id")

    def list_crops(self, tracklet_id: str) -> list[TrackletCrop]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM tracklet_crops WHERE tracklet_id = ? ORDER BY ts, crop_id",
                (tracklet_id,),
            ).fetchall()
        return [TrackletCrop(**dict(row)) for row in rows]

    def list_crops_for_cluster(self, cluster_id: str) -> list[TrackletCrop]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT c.* FROM tracklet_crops c
                JOIN tracklets t ON t.tracklet_id = c.tracklet_id
                WHERE t.cluster_id = ? ORDER BY c.ts, c.crop_id
                """,
                (cluster_id,),
            ).fetchall()
        return [TrackletCrop(**dict(row)) for row in rows]

    def bulk_upsert_embeddings(
        self, embeddings: Iterable[TrackletEmbedding]
    ) -> None:
        self._bulk_upsert("tracklet_embeddings", embeddings, "tracklet_id")

    def list_embeddings(self, source_id: str) -> list[TrackletEmbedding]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT e.* FROM tracklet_embeddings e
                JOIN tracklets t ON t.tracklet_id = e.tracklet_id
                WHERE t.source_id = ? ORDER BY e.tracklet_id
                """,
                (source_id,),
            ).fetchall()
        return [TrackletEmbedding(**dict(row)) for row in rows]

    def bulk_upsert_clusters(self, clusters: Iterable[IdentityCluster]) -> None:
        self._bulk_upsert("identity_clusters", clusters, "cluster_id")

    def list_clusters(self, source_id: str) -> list[IdentityCluster]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM identity_clusters
                WHERE source_id = ? ORDER BY screen_time_s DESC, cluster_id
                """,
                (source_id,),
            ).fetchall()
        return [IdentityCluster(**dict(row)) for row in rows]

    def replace_candidate_clusters(
        self,
        source_id: str,
        clusters: Iterable[IdentityCluster],
        assignments: dict[str, str],
    ) -> None:
        cluster_rows = [asdict(cluster) for cluster in clusters]
        with self.database.transaction(immediate=True) as connection:
            connection.execute(
                """
                UPDATE tracklets SET cluster_id = NULL
                WHERE source_id = ? AND synthetic = 0
                """,
                (source_id,),
            )
            connection.execute(
                "DELETE FROM identity_clusters WHERE source_id = ? AND status = 'candidate'",
                (source_id,),
            )
            if cluster_rows:
                columns = list(cluster_rows[0])
                connection.executemany(
                    f"INSERT INTO identity_clusters ({', '.join(columns)}) "
                    f"VALUES ({', '.join('?' for _ in columns)}) "
                    "ON CONFLICT(cluster_id) DO UPDATE SET "
                    + ", ".join(
                        f"{column} = excluded.{column}"
                        for column in columns
                        if column != "cluster_id"
                    ),
                    [tuple(row[column] for column in columns) for row in cluster_rows],
                )
            connection.executemany(
                """
                UPDATE tracklets SET cluster_id = ?
                WHERE tracklet_id = ? AND source_id = ?
                  AND COALESCE(cluster_assignment, 'auto') != 'user_removed'
                  AND synthetic = 0
                """,
                [
                    (cluster_id, tracklet_id, source_id)
                    for tracklet_id, cluster_id in assignments.items()
                ],
            )

    def bulk_insert_jersey_votes(self, votes: Iterable[JerseyVote]) -> None:
        self._bulk_upsert("jersey_votes", votes, "vote_id")

    def replace_jersey_votes(
        self, tracklet_id: str, votes: Iterable[JerseyVote]
    ) -> None:
        rows = [asdict(vote) for vote in votes]
        with self.database.transaction(immediate=True) as connection:
            connection.execute(
                "DELETE FROM jersey_votes WHERE tracklet_id = ?", (tracklet_id,)
            )
            if rows:
                columns = list(rows[0])
                connection.executemany(
                    f"INSERT INTO jersey_votes ({', '.join(columns)}) "
                    f"VALUES ({', '.join('?' for _ in columns)})",
                    [tuple(row[column] for column in columns) for row in rows],
                )

    def replace_jersey_votes_batch(
        self,
        votes_by_tracklet: dict[str, list[JerseyVote]],
    ) -> None:
        if not votes_by_tracklet:
            return
        rows = [
            asdict(vote)
            for votes in votes_by_tracklet.values()
            for vote in votes
        ]
        with self.database.transaction(immediate=True) as connection:
            connection.executemany(
                "DELETE FROM jersey_votes WHERE tracklet_id = ?",
                [(tracklet_id,) for tracklet_id in votes_by_tracklet],
            )
            if rows:
                columns = list(rows[0])
                connection.executemany(
                    f"INSERT INTO jersey_votes ({', '.join(columns)}) "
                    f"VALUES ({', '.join('?' for _ in columns)})",
                    [tuple(row[column] for column in columns) for row in rows],
                )

    def list_jersey_votes_for_tracklet(
        self, tracklet_id: str
    ) -> list[JerseyVote]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM jersey_votes WHERE tracklet_id = ? ORDER BY ts, vote_id",
                (tracklet_id,),
            ).fetchall()
        return [JerseyVote(**dict(row)) for row in rows]

    def list_jersey_votes(self, source_id: str) -> list[JerseyVote]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT v.* FROM jersey_votes v
                JOIN tracklets t ON t.tracklet_id = v.tracklet_id
                WHERE t.source_id = ? ORDER BY v.ts, v.vote_id
                """,
                (source_id,),
            ).fetchall()
        return [JerseyVote(**dict(row)) for row in rows]

    def list_jersey_votes_for_cluster(self, cluster_id: str) -> list[JerseyVote]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT v.* FROM jersey_votes v
                JOIN tracklets t ON t.tracklet_id = v.tracklet_id
                WHERE t.cluster_id = ? ORDER BY v.ts, v.vote_id
                """,
                (cluster_id,),
            ).fetchall()
        return [JerseyVote(**dict(row)) for row in rows]

    def _bulk_upsert(self, table: str, items: Iterable[object], key: str) -> None:
        rows = [asdict(item) for item in items]
        if not rows:
            return
        columns = list(rows[0])
        updates = [column for column in columns if column != key]
        sql = (
            f"INSERT INTO {table} ({', '.join(columns)}) "
            f"VALUES ({', '.join('?' for _ in columns)}) "
            f"ON CONFLICT({key}) DO UPDATE SET "
            + ", ".join(f"{column} = excluded.{column}" for column in updates)
        )
        with self.database.connect() as connection:
            connection.executemany(
                sql, [tuple(row[column] for column in columns) for row in rows]
            )
