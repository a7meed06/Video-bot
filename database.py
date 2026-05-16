from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, BigInteger
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'

    id = Column(BigInteger, primary_key=True)
    username = Column(String)
    first_name = Column(String)
    daily_downloads = Column(Integer, default=0)
    total_downloads = Column(Integer, default=0)
    last_reset = Column(DateTime, default=datetime.utcnow)
    joined_at = Column(DateTime, default=datetime.utcnow)
    is_banned = Column(Boolean, default=False)

class Download(Base):
    __tablename__ = 'downloads'

    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger)
    url = Column(String)
    platform = Column(String)
    title = Column(String)
    quality = Column(String)
    file_size = Column(Integer)
    status = Column(String, default='pending')
    error_message = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

class Database:
    def __init__(self, db_url):
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def get_user(self, user_id):
        session = self.Session()
        user = session.query(User).filter_by(id=user_id).first()
        if not user:
            user = User(id=user_id)
            session.add(user)
            session.commit()
        session.close()
        return user

    def can_download(self, user_id):
        from config import Config
        user = self.get_user(user_id)
        if user.is_banned:
            return False, "🚷 حسابك محظور"

        now = datetime.utcnow()
        if now - user.last_reset > timedelta(days=1):
            user.daily_downloads = 0
            user.last_reset = now
            session = self.Session()
            session.merge(user)
            session.commit()
            session.close()

        if user.daily_downloads >= Config.DAILY_LIMIT:
            return False, f"⚠️ وصلت للحد اليومي ({Config.DAILY_LIMIT} فيديو). جرب بكرة!"

        return True, "✅ يمكنك التحميل"

    def add_download(self, user_id, url, platform, title):
        session = self.Session()
        dl = Download(user_id=user_id, url=url, platform=platform, title=title)
        session.add(dl)
        session.commit()
        dl_id = dl.id
        session.close()
        return dl_id

    def complete_download(self, dl_id, quality, file_size, status='completed'):
        session = self.Session()
        dl = session.query(Download).filter_by(id=dl_id).first()
        if dl:
            dl.quality = quality
            dl.file_size = file_size
            dl.status = status
            dl.completed_at = datetime.utcnow()
            user = session.query(User).filter_by(id=dl.user_id).first()
            if user:
                user.daily_downloads += 1
                user.total_downloads += 1
            session.commit()
        session.close()

    def get_stats(self):
        session = self.Session()
        stats = {
            'total_users': session.query(User).count(),
            'total_downloads': session.query(Download).filter_by(status='completed').count(),
            'today_downloads': session.query(Download).filter(
                Download.created_at >= datetime.utcnow() - timedelta(days=1)
            ).count(),
            'active_today': session.query(Download).filter(
                Download.created_at >= datetime.utcnow() - timedelta(days=1)
            ).distinct(Download.user_id).count()
        }
        session.close()
        return stats

    def get_user_stats(self, user_id):
        session = self.Session()
        user = session.query(User).filter_by(id=user_id).first()
        downloads = session.query(Download).filter_by(user_id=user_id).order_by(Download.created_at.desc()).limit(10).all()
        session.close()
        return user, downloads

    def ban_user(self, user_id, ban=True):
        session = self.Session()
        user = session.query(User).filter_by(id=user_id).first()
        if user:
            user.is_banned = ban
            session.commit()
        session.close()
