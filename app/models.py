import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKeyConstraint, Index, Integer, JSON, String, Text, text
from sqlalchemy.dialects.mysql import CHAR, INTEGER, LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.mysql_core import Base


class Paths(Base):
    __tablename__ = 'paths'

    pid: Mapped[str] = mapped_column(CHAR(36, charset='ascii', collation='ascii_general_ci'), primary_key=True,
                                     comment='Path ID (UUID)')
    description: Mapped[Optional[str]] = mapped_column(Text, comment='Path description')

    units: Mapped[list['Units']] = relationship('Units', back_populates='paths')


class Users(Base):
    __tablename__ = 'users'
    __table_args__ = (
        Index('uk_users_uname', 'uname', unique=True),
    )

    uid: Mapped[str] = mapped_column(CHAR(36, charset='ascii', collation='ascii_general_ci'), primary_key=True,
                                     comment='User ID (UUID)')
    uname: Mapped[str] = mapped_column(String(50), nullable=False, comment='Username')
    password: Mapped[str] = mapped_column(String(16), nullable=False,
                                          server_default='123456', comment='User Password')
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False,
                                                          server_default=text('CURRENT_TIMESTAMP'),
                                                          comment='Account created time')
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=text(
        'CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'), comment='Last updated time')

    resources: Mapped[list['Resources']] = relationship('Resources', back_populates='users')
    sessions: Mapped[list['Sessions']] = relationship('Sessions', back_populates='users')
    units: Mapped[list['Units']] = relationship('Units', back_populates='users')
    exercises: Mapped[list['Exercises']] = relationship('Exercises', back_populates='users')
    flashcards: Mapped[list['Flashcards']] = relationship('Flashcards', back_populates='users')


class Resources(Base):
    __tablename__ = 'resources'
    __table_args__ = (
        ForeignKeyConstraint(['uid'], ['users.uid'], ondelete='CASCADE', name='fk_resources_uid'),
        Index('idx_resources_rtype', 'rtype'),
        Index('idx_resources_uid_created', 'uid', 'created_at')
    )

    rid: Mapped[str] = mapped_column(CHAR(36, charset='ascii', collation='ascii_general_ci'), primary_key=True,
                                     comment='Resource ID (UUID)')
    uid: Mapped[str] = mapped_column(CHAR(36, charset='ascii', collation='ascii_general_ci'), nullable=False,
                                     comment='Owner user ID (UUID)')
    # NOTE:
    # Prefer `storage_provider + storage_key` and derive the public URL at read time.
    # Keep `url` for backward compatibility with existing records / external resources.
    url: Mapped[Optional[str]] = mapped_column(CHAR(256), comment='Resource URL (legacy or external)')
    storage_provider: Mapped[Optional[str]] = mapped_column(
        String(20),
        comment='Storage provider (local/oss)',
    )
    storage_key: Mapped[Optional[str]] = mapped_column(
        String(512),
        comment='Storage object key',
    )
    rname: Mapped[str] = mapped_column(String(100), nullable=False, comment='Resource name')
    rtype: Mapped[str] = mapped_column(String(20), nullable=False, comment='Resource type (doc/video/audio/etc.)')
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False,
                                                          server_default=text('CURRENT_TIMESTAMP'),
                                                          comment='Created time')
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, server_default=text(
        'CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'), comment='Updated time')
    content: Mapped[Optional[str]] = mapped_column(LONGTEXT, comment='Raw extracted text content')
    summary: Mapped[Optional[str]] = mapped_column(Text, comment='Generated summary (optional)')
    keywords: Mapped[Optional[dict]] = mapped_column(JSON, comment='Keywords (JSON array/object)')
    status: Mapped[Optional[int]] = mapped_column(Integer, server_default=text("'0'"),
                                                  comment='0=pending, 1=parsing, 2=parsed')

    users: Mapped['Users'] = relationship('Users', back_populates='resources')
    session_resources: Mapped[list['SessionResources']] = relationship('SessionResources', back_populates='resources')


class Sessions(Base):
    __tablename__ = 'sessions'
    __table_args__ = (
        ForeignKeyConstraint(['uid'], ['users.uid'], ondelete='CASCADE', name='fk_sessions_uid'),
        Index('idx_sessions_uid_created', 'uid', 'created_at')
    )

    sid: Mapped[str] = mapped_column(CHAR(36, charset='ascii', collation='ascii_general_ci'), primary_key=True,
                                     comment='Session ID (UUID)')
    uid: Mapped[str] = mapped_column(CHAR(36, charset='ascii', collation='ascii_general_ci'), nullable=False,
                                     comment='Owner user ID (UUID)')
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False,
                                                          server_default=text('CURRENT_TIMESTAMP'),
                                                          comment='Session start time')

    users: Mapped['Users'] = relationship('Users', back_populates='sessions')
    session_resources: Mapped[list['SessionResources']] = relationship('SessionResources', back_populates='sessions')
    units: Mapped[list['Units']] = relationship('Units', back_populates='sessions')

class SessionResources(Base):
    __tablename__ = 'session_resources'
    __table_args__ = (
        ForeignKeyConstraint(['rid'], ['resources.rid'], ondelete='CASCADE', name='fk_session_resources_rid'),
        ForeignKeyConstraint(['sid'], ['sessions.sid'], ondelete='CASCADE', name='fk_session_resources_sid'),
        Index('idx_session_resources_rid', 'rid')
    )

    sid: Mapped[str] = mapped_column(CHAR(36, charset='ascii', collation='ascii_general_ci'), primary_key=True,
                                     comment='Session ID (UUID)')
    rid: Mapped[str] = mapped_column(CHAR(36, charset='ascii', collation='ascii_general_ci'), primary_key=True,
                                     comment='Resource ID (UUID)')
    added_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False,
                                                        server_default=text('CURRENT_TIMESTAMP'),
                                                        comment='Time resource added to session')

    resources: Mapped['Resources'] = relationship('Resources', back_populates='session_resources')
    sessions: Mapped['Sessions'] = relationship('Sessions', back_populates='session_resources')


class Units(Base):
    __tablename__ = 'units'
    __table_args__ = (
        ForeignKeyConstraint(['pid'], ['paths.pid'], ondelete='CASCADE', name='fk_units_pid'),
        ForeignKeyConstraint(['sid'], ['sessions.sid'], ondelete='SET NULL', name='fk_units_sid'),
        ForeignKeyConstraint(['uid'], ['users.uid'], ondelete='CASCADE', name='fk_units_uid'),
        Index('idx_units_pid', 'pid'),
        Index('idx_units_sid', 'sid'),
        Index('idx_units_uid_created', 'uid', 'created_at')
    )

    unit_id: Mapped[str] = mapped_column(CHAR(36, charset='ascii', collation='ascii_general_ci'), primary_key=True,
                                         comment='Unit ID (UUID)')
    pid: Mapped[str] = mapped_column(CHAR(36, charset='ascii', collation='ascii_general_ci'), nullable=False,
                                     comment='Path ID (UUID)')
    uid: Mapped[str] = mapped_column(CHAR(36, charset='ascii', collation='ascii_general_ci'), nullable=False,
                                     comment='Owner user ID (UUID)')
    goal: Mapped[str] = mapped_column(String(200), nullable=False, comment='Learning goal')
    guide: Mapped[str] = mapped_column(Text, nullable=False, comment='Learning guide/outline')
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False,
                                                          server_default=text('CURRENT_TIMESTAMP'),
                                                          comment='Created time')
    sid: Mapped[Optional[str]] = mapped_column(CHAR(36, charset='ascii', collation='ascii_general_ci'),
                                               comment='Optional session ID (UUID)')
    core_concepts: Mapped[Optional[dict]] = mapped_column(JSON, comment='Core concepts (JSON array/object)')
    completed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, comment='Completed time (optional)')
    status: Mapped[Optional[int]] = mapped_column(Integer, server_default=text("'0'"),
                                                  comment='0=not_started, 1=in_progress, 2=completed')

    paths: Mapped['Paths'] = relationship('Paths', back_populates='units')
    sessions: Mapped[Optional['Sessions']] = relationship('Sessions', back_populates='units')
    users: Mapped['Users'] = relationship('Users', back_populates='units')
    exercises: Mapped[list['Exercises']] = relationship('Exercises', back_populates='unit')
    flashcards: Mapped[list['Flashcards']] = relationship('Flashcards', back_populates='unit')


class Exercises(Base):
    __tablename__ = 'exercises'
    __table_args__ = (
        ForeignKeyConstraint(['uid'], ['users.uid'], ondelete='CASCADE', name='fk_exercises_uid'),
        ForeignKeyConstraint(['unit_id'], ['units.unit_id'], ondelete='CASCADE', name='fk_exercises_unit_id'),
        Index('idx_exercises_uid_created', 'uid', 'created_at'),
        Index('idx_exercises_unit_id', 'unit_id')
    )

    eid: Mapped[str] = mapped_column(CHAR(36, charset='ascii', collation='ascii_general_ci'), primary_key=True,
                                     comment='Exercise ID (UUID)')
    unit_id: Mapped[str] = mapped_column(CHAR(36, charset='ascii', collation='ascii_general_ci'), nullable=False,
                                         comment='Unit ID (UUID)')
    uid: Mapped[str] = mapped_column(CHAR(36, charset='ascii', collation='ascii_general_ci'), nullable=False,
                                     comment='Owner user ID (UUID)')
    question: Mapped[str] = mapped_column(Text, nullable=False, comment='Question text')
    correct_answer: Mapped[str] = mapped_column(Text, nullable=False, comment='Correct answer')
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False,
                                                          server_default=text('CURRENT_TIMESTAMP'),
                                                          comment='Created time')
    options: Mapped[Optional[dict]] = mapped_column(JSON, comment='Options (JSON array/object, optional)')
    explanation: Mapped[Optional[str]] = mapped_column(Text, comment='Explanation (optional)')

    users: Mapped['Users'] = relationship('Users', back_populates='exercises')
    unit: Mapped['Units'] = relationship('Units', back_populates='exercises')


class Flashcards(Base):
    __tablename__ = 'flashcards'
    __table_args__ = (
        ForeignKeyConstraint(['uid'], ['users.uid'], ondelete='CASCADE', name='fk_flashcards_uid'),
        ForeignKeyConstraint(['unit_id'], ['units.unit_id'], ondelete='CASCADE', name='fk_flashcards_unit_id'),
        Index('idx_flashcards_uid_created', 'uid', 'created_at'),
        Index('idx_flashcards_unit_id', 'unit_id')
    )

    fcid: Mapped[str] = mapped_column(CHAR(36, charset='ascii', collation='ascii_general_ci'), primary_key=True,
                                      comment='Flashcard ID (UUID)')
    unit_id: Mapped[str] = mapped_column(CHAR(36, charset='ascii', collation='ascii_general_ci'), nullable=False,
                                         comment='Unit ID (UUID)')
    uid: Mapped[str] = mapped_column(CHAR(36, charset='ascii', collation='ascii_general_ci'), nullable=False,
                                     comment='Owner user ID (UUID)')
    question: Mapped[str] = mapped_column(Text, nullable=False, comment='Front side / question')
    answer: Mapped[str] = mapped_column(Text, nullable=False, comment='Back side / answer')
    review_count: Mapped[int] = mapped_column(INTEGER(unsigned=True), nullable=False, server_default=text("'0'"),
                                              comment='Review count')
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False,
                                                          server_default=text('CURRENT_TIMESTAMP'),
                                                          comment='Created time')
    last_reviewed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime,
                                                                          comment='Last reviewed time (optional)')

    users: Mapped['Users'] = relationship('Users', back_populates='flashcards')
    unit: Mapped['Units'] = relationship('Units', back_populates='flashcards')
