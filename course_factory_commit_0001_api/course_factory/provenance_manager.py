from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .artifact_models import ManagedArtifact
from .provenance_models import ProvenanceRecord


class ProvenanceManager:
    def __init__(self, output_dir: str | Path | None = None) -> None:
        self.records: dict[str, ProvenanceRecord] = {}
        self.output_dir = Path(output_dir) if output_dir else None
        if self.output_dir:
            self.output_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def checksum(value) -> str:
        data = json.dumps(
            value,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
        return hashlib.sha256(data).hexdigest()

    def register(
        self,
        *,
        artifact: ManagedArtifact,
        agent_name: str,
        agent_version: str,
        llm_model: str | None,
        prompt,
        inputs: list,
        output,
    ) -> ProvenanceRecord:
        record = ProvenanceRecord(
            artifact_id=artifact.artifact_id,
            artifact_type=artifact.artifact_type,
            agent_name=agent_name,
            agent_version=agent_version,
            llm_model=llm_model,
            prompt_checksum=self.checksum(prompt),
            input_checksums=tuple(
                self.checksum(item) for item in inputs
            ),
            output_checksum=self.checksum(output),
            parent_artifacts=artifact.dependencies,
        )
        self.records[artifact.artifact_id] = record

        if self.output_dir:
            target = self.output_dir / (
                artifact.artifact_id
                .replace("/", "__")
                .replace(":", "__")
                + ".json"
            )
            target.write_text(
                record.model_dump_json(indent=2),
                encoding="utf-8",
            )

        return record

    def get(self, artifact_id: str) -> ProvenanceRecord:
        return self.records[artifact_id]

    def all(self) -> tuple[ProvenanceRecord, ...]:
        return tuple(
            self.records[key]
            for key in sorted(self.records)
        )
