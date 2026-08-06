from __future__ import annotations

from hashlib import sha1

from src.domain.models.selection import AppearanceSegment
from src.storage.analysis_repository import AnalysisRepository
from src.storage.db import Database
from src.storage.selection_repository import SelectionRepository
from src.storage.source_repository import SourceRepository


class TimelineService:
    def __init__(self, database: Database, *, settings=None, artifacts=None, evidence=None) -> None:
        self.analysis = AnalysisRepository(database)
        self.selection = SelectionRepository(database)
        self.sources = SourceRepository(database)
        self.settings = settings
        self.artifacts = artifacts
        self.evidence = evidence

    def rebuild(self, project_id: str, cluster_id: str) -> dict:
        source = self.sources.get_for_project(project_id)
        if source is None:
            raise KeyError(project_id)

        tracklets = [
            tracklet for tracklet in self.analysis.list_tracklets(source.source_id)
            if tracklet.cluster_id == cluster_id
            and tracklet.cluster_assignment != "user_removed"
        ]

        spans = sorted([(t.start_ts, t.end_ts) for t in tracklets], key=lambda x: x[0])

        if not spans:
            self.selection.replace_segments(project_id, [])
            return self.coverage(project_id, float(source.duration_s or 0.0))

        # MERGE
        merged_spans = []
        curr_start, curr_end = spans[0]
        for i in range(1, len(spans)):
            next_start, next_end = spans[i]
            if next_start - curr_end < 2.0:
                curr_end = max(curr_end, next_end)
            else:
                merged_spans.append((curr_start, curr_end))
                curr_start, curr_end = next_start, next_end
        merged_spans.append((curr_start, curr_end))

        # DROP
        surviving_spans = [span for span in merged_spans if (span[1] - span[0]) >= 1.5]

        # PAD
        duration = float(source.duration_s or 0.0)
        padded_spans = []
        for start, end in surviving_spans:
            new_start = max(0.0, start - 1.5)
            if duration > 0:
                new_end = min(duration, end + 1.5)
            else:
                new_end = end + 1.5
            padded_spans.append((new_start, new_end))

        # RE-MERGE
        final_spans = []
        if padded_spans:
            padded_spans.sort(key=lambda x: x[0])
            curr_start, curr_end = padded_spans[0]
            for i in range(1, len(padded_spans)):
                next_start, next_end = padded_spans[i]
                if next_start <= curr_end:
                    curr_end = max(curr_end, next_end)
                else:
                    final_spans.append((curr_start, curr_end))
                    curr_start, curr_end = next_start, next_end
            final_spans.append((curr_start, curr_end))

        segments = []
        for start, end in final_spans:
            segment_id = f"segment-{sha1(f'{project_id}:{cluster_id}:{round(start,3)}:{round(end,3)}'.encode()).hexdigest()[:16]}"
            segments.append(AppearanceSegment(
                segment_id=segment_id,
                project_id=project_id,
                cluster_id=cluster_id,
                start_ts=start,
                end_ts=end,
                score=(end - start),
                included=True
            ))

        self.selection.replace_segments(project_id, segments)
        return self.coverage(project_id, duration)

    def coverage(self, project_id: str, duration_s: float | None = None) -> dict:
        segments = self.selection.list_segments(project_id)
        sorted_segments = sorted(segments, key=lambda s: s.start_ts)
        
        total_s = sum(max(0.0, s.end_ts - s.start_ts) for s in sorted_segments)
        
        gaps = []
        cursor = 0.0
        for segment in sorted_segments:
            if segment.start_ts > cursor:
                gaps.append({"start_ts": cursor, "end_ts": segment.start_ts})
            cursor = max(cursor, segment.end_ts)
            
        if duration_s is not None and duration_s > cursor:
            gaps.append({"start_ts": cursor, "end_ts": duration_s})
            
        return {
            "segment_count": len(segments),
            "total_s": total_s,
            "gaps": gaps,
        }

    def timeline(self, project_id: str) -> dict:
        segments = self.selection.list_segments(project_id)
        sorted_segments = sorted(segments, key=lambda s: s.start_ts)

        total_s = sum(s.end_ts - s.start_ts for s in sorted_segments if s.end_ts > s.start_ts)
        included_count = sum(1 for s in sorted_segments if s.included)

        # Active tracklets (per cluster) so "Not them" can remove a segment's
        # underlying tracklets as negative evidence.
        source = self.sources.get_for_project(project_id)
        tracklets = (
            [
                tracklet
                for tracklet in self.analysis.list_tracklets(source.source_id)
                if tracklet.cluster_assignment != "user_removed"
            ]
            if source is not None
            else []
        )

        segment_list = []
        for seg in sorted_segments:
            if self.artifacts is not None:
                thumbnail_uri = self.artifacts.evidence_media_uri(project_id, f"segment-{seg.segment_id}.jpg")
                preview_clip_uri = self.artifacts.evidence_media_uri(project_id, f"segment-{seg.segment_id}.mp4")
            else:
                thumbnail_uri = f"/projects/{project_id}/evidence-media/segment-{seg.segment_id}.jpg"
                preview_clip_uri = f"/projects/{project_id}/evidence-media/segment-{seg.segment_id}.mp4"

            tracklet_ids = [
                tracklet.tracklet_id
                for tracklet in tracklets
                if tracklet.cluster_id == seg.cluster_id
                and tracklet.start_ts < seg.end_ts
                and tracklet.end_ts > seg.start_ts
            ]

            segment_list.append({
                "segment_id": seg.segment_id,
                "start_ts": seg.start_ts,
                "end_ts": seg.end_ts,
                "score": seg.score if seg.score is not None else (seg.end_ts - seg.start_ts),
                "included": bool(seg.included),
                "thumbnail_uri": thumbnail_uri,
                "preview_clip_uri": preview_clip_uri,
                "tracklet_ids": tracklet_ids,
            })

        return {
            "summary": {
                "segment_count": len(segments),
                "total_s": total_s,
                "included_count": included_count
            },
            "segments": segment_list
        }

    def set_segment(self, project_id: str, segment_id: str, *, included: bool | None = None, start_ts: float | None = None, end_ts: float | None = None) -> dict:
        segments = self.selection.list_segments(project_id)
        target_segment = next((s for s in segments if s.segment_id == segment_id), None)
        
        if target_segment is None:
            raise KeyError(segment_id)
        
        if included is not None:
            target_segment.included = included
        if start_ts is not None:
            target_segment.start_ts = start_ts
        if end_ts is not None:
            target_segment.end_ts = end_ts
            
        self.selection.replace_segments(project_id, segments)
        return {
            "segment_id": segment_id,
            "start_ts": target_segment.start_ts,
            "end_ts": target_segment.end_ts,
            "included": bool(target_segment.included)
        }
