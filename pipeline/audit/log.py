"""Append-only audit log DB table and HTML packet renderer."""

from __future__ import annotations

import html
import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.database import Base
from pipeline.audit.models import AuditPacket


class AuditLogRecord(Base):
    """Append-only audit log row — one row per answered question."""

    __tablename__ = "audit_log"

    audit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    user_role: Mapped[str] = mapped_column(String(128), nullable=False, default="anonymous")
    plan_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    payer: Mapped[str | None] = mapped_column(String(256), nullable=True)
    cpt: Mapped[str | None] = mapped_column(String(16), nullable=True)
    confidence: Mapped[str] = mapped_column(String(16), nullable=False)
    abstained: Mapped[bool] = mapped_column(nullable=False, default=False)
    model_provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    packet_json: Mapped[dict] = mapped_column(JSONB, nullable=False)

    def __repr__(self) -> str:
        return f"<AuditLogRecord {self.audit_id} confidence={self.confidence}>"


def append_audit_log(session: Session, packet: AuditPacket) -> AuditLogRecord:
    """Write one immutable audit log row. Does NOT update existing rows."""
    record = AuditLogRecord(
        audit_id=packet.audit_id,
        created_at=packet.created_at,
        question=packet.question,
        user_role=packet.user_role,
        plan_id=packet.plan_id,
        payer=packet.payer,
        cpt=packet.cpt,
        confidence=packet.confidence,
        abstained=packet.abstained,
        model_provider=packet.model_provider,
        model_name=packet.model_name,
        packet_json=packet.model_dump(mode="json"),
    )
    session.add(record)
    session.commit()
    return record


def get_audit_record(session: Session, audit_id: str) -> AuditLogRecord | None:
    return session.get(AuditLogRecord, uuid.UUID(audit_id))


def render_html(packet: AuditPacket) -> str:
    """Render the audit packet as a styled HTML report."""
    def esc(v: object) -> str:
        return html.escape(str(v) if v is not None else "—")

    citations_rows = ""
    for c in packet.citations:
        citations_rows += f"""
        <tr>
          <td>{esc(c.policy_id)}</td>
          <td>{esc(c.section_label)}</td>
          <td>{esc(c.effective_date)}</td>
          <td>{esc(c.expiry_date)}</td>
          <td><span class="badge {esc(c.dq_status)}">{esc(c.dq_status)}</span></td>
          <td class="snippet">{esc(c.chunk_text_snippet)}</td>
        </tr>"""

    missing_html = "".join(f"<li>{esc(m)}</li>" for m in packet.missing_data) or "<li>None</li>"

    conf_class = packet.confidence.lower().replace(" ", "-")
    abstain_banner = ""
    if packet.abstained:
        abstain_banner = f'<div class="abstain-banner">⛔ ABSTAINED — {esc(packet.abstain_reason)}</div>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>MediGovern RAG — Audit Packet {esc(packet.audit_id)}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
           max-width: 960px; margin: 40px auto; padding: 0 20px; color: #1a1a2e; }}
    h1 {{ color: #16213e; border-bottom: 3px solid #0f3460; padding-bottom: 8px; }}
    h2 {{ color: #0f3460; margin-top: 28px; }}
    .meta {{ background: #f0f4ff; padding: 16px; border-radius: 8px; margin: 16px 0; }}
    .meta span {{ font-weight: 600; }}
    .answer {{ background: #fff; border: 1px solid #dde; padding: 16px;
               border-radius: 8px; white-space: pre-wrap; line-height: 1.6; }}
    .confidence {{ display: inline-block; padding: 4px 14px; border-radius: 20px;
                   font-weight: 700; font-size: 14px; }}
    .high {{ background: #d4edda; color: #155724; }}
    .medium {{ background: #fff3cd; color: #856404; }}
    .low {{ background: #f8d7da; color: #721c24; }}
    .abstain {{ background: #e2e3e5; color: #383d41; }}
    .abstain-banner {{ background: #f8d7da; border: 2px solid #f5c6cb;
                       padding: 12px 16px; border-radius: 6px; font-weight: 600;
                       color: #721c24; margin: 16px 0; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 13px; }}
    th {{ background: #0f3460; color: white; text-align: left; padding: 8px 10px; }}
    td {{ padding: 7px 10px; border-bottom: 1px solid #eee; vertical-align: top; }}
    tr:hover td {{ background: #f5f7ff; }}
    .snippet {{ color: #555; font-size: 12px; max-width: 280px;
                white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
    .badge {{ padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; }}
    .badge.passed {{ background: #d4edda; color: #155724; }}
    .badge.warning {{ background: #fff3cd; color: #856404; }}
    .badge.quarantined {{ background: #f8d7da; color: #721c24; }}
    .filters {{ font-size: 13px; color: #555; }}
    footer {{ margin-top: 40px; font-size: 12px; color: #888; border-top: 1px solid #eee;
              padding-top: 12px; }}
  </style>
</head>
<body>
  <h1>MediGovern RAG — Audit Packet</h1>
  <div class="meta">
    <div><span>Audit ID:</span> {esc(packet.audit_id)}</div>
    <div><span>Timestamp:</span> {esc(packet.created_at.isoformat())}</div>
    <div><span>User Role:</span> {esc(packet.user_role)}</div>
    <div><span>Model:</span> {esc(packet.model_provider)} / {esc(packet.model_name)}</div>
  </div>

  <h2>Question</h2>
  <p>{esc(packet.question)}</p>

  <h2>Filters Applied</h2>
  <p class="filters">{esc(json.dumps(packet.filters_applied))}</p>

  <h2>Confidence</h2>
  <p>
    <span class="confidence {conf_class}">{esc(packet.confidence)}</span>
    &nbsp; {esc(packet.confidence_rationale)}
  </p>

  {abstain_banner}

  <h2>Answer</h2>
  <div class="answer">{esc(packet.answer)}</div>

  <h2>Citations ({len(packet.citations)})</h2>
  <table>
    <thead><tr>
      <th>Policy ID</th><th>Section</th><th>Effective</th>
      <th>Expiry</th><th>DQ Status</th><th>Snippet</th>
    </tr></thead>
    <tbody>{citations_rows}</tbody>
  </table>

  <h2>Missing Data</h2>
  <ul>{missing_html}</ul>

  <footer>
    ⚠ SYNTHETIC DATA — MediGovern RAG demonstration only. Not for clinical use.<br>
    All records are synthetic; no real PHI is present.
  </footer>
</body>
</html>"""
