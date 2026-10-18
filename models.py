from sqlalchemy import ForeignKey, Integer, LargeBinary, MetaData, Text, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(table_name)s_%(column_0_name)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


class CategoryModel(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)


class PriorityModel(Base):
    __tablename__ = "priorities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)


class SupportRequestModel(Base):
    __tablename__ = "support_requests"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    book: Mapped[str] = mapped_column(Text, nullable=False)
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id"), nullable=False
    )
    priority_id: Mapped[int] = mapped_column(
        ForeignKey("priorities.id"), nullable=False
    )
    created_at: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("CURRENT_TIMESTAMP")
    )
    attachments: Mapped[list["SupportAttachmentModel"]] = relationship(
        back_populates="support_request", cascade="all, delete-orphan"
    )


class SupportAttachmentModel(Base):
    __tablename__ = "support_attachments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("support_requests.id", ondelete="CASCADE"),
        nullable=False,
    )
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    support_request: Mapped[SupportRequestModel] = relationship(
        back_populates="attachments"
    )
