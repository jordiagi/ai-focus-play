import React from "react";

export function OutputList({ outputs }: { outputs: Array<{ outputId: string; exportStatus: string; downloadUri?: string }> }): JSX.Element {
  return (
    <section>
      <h2>Exports</h2>
      <ul>
        {outputs.map((output) => (
          <li key={output.outputId}>
            {output.outputId} - {output.exportStatus} {output.downloadUri ? <a href={output.downloadUri}>Download</a> : null}
          </li>
        ))}
      </ul>
    </section>
  );
}

