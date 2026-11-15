import os
from pathlib import Path
from typing import Protocol

import boto3
from sqlalchemy import JSON, ForeignKey, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

DATA = Path(os.getenv("DATA_DIR", ".data"))


class Base(DeclarativeBase):
    pass


class Asset(Base):
    __tablename__ = "assets"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner: Mapped[str] = mapped_column(String(64), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    mime: Mapped[str] = mapped_column(String(32))
    width: Mapped[int]
    height: Mapped[int]
    size: Mapped[int]


class AuditRecord(Base):
    __tablename__ = "audits"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id"), index=True)
    request: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict] = mapped_column(JSON)
    provider_model: Mapped[str] = mapped_column(String(160))
    prompt_version: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[str] = mapped_column(String(40))


class PromptRevision(Base):
    __tablename__ = "prompt_revisions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    audit_id: Mapped[str] = mapped_column(ForeignKey("audits.id"), index=True)
    treatment: Mapped[str] = mapped_column(String(32))
    text: Mapped[str] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String(40))


class ObjectStore(Protocol):
    def put(self, key: str, data: bytes, mime: str) -> None: ...
    def get(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...


class LocalStore:
    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)

    def put(self, key, data, mime):
        target = self.root / key
        pending = target.with_suffix(".tmp")
        try:
            pending.write_bytes(data)
            pending.replace(target)
        finally:
            pending.unlink(missing_ok=True)

    def get(self, key):
        return (self.root / key).read_bytes()

    def delete(self, key):
        (self.root / key).unlink(missing_ok=True)


class S3Store:
    def __init__(self, bucket: str):
        self.bucket = bucket
        self.client = boto3.client("s3", endpoint_url=os.getenv("S3_ENDPOINT_URL"))

    def put(self, key, data, mime):
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=mime)

    def get(self, key):
        body = self.client.get_object(Bucket=self.bucket, Key=key)["Body"]
        try:
            return body.read()
        finally:
            body.close()

    def delete(self, key):
        self.client.delete_object(Bucket=self.bucket, Key=key)


def make_storage():
    DATA.mkdir(parents=True, exist_ok=True)
    url = os.getenv("DATABASE_URL", f"sqlite:///{DATA / 'director.db'}")
    engine = create_engine(url, pool_pre_ping=True)
    bucket = os.getenv("S3_BUCKET")
    objects = S3Store(bucket) if bucket else LocalStore(DATA / "originals")
    return engine, objects
