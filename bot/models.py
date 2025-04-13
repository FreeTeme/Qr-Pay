from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True)
    full_name = Column(String)
    gender = Column(String)
    email = Column(String)
    birth_date = Column(DateTime)
    username = Column(String)
    businesses = relationship("UserBusiness", back_populates="user")

class Business(Base):
    __tablename__ = 'businesses'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    conversion_rate = Column(Float, default=10.0)
    admin_id = Column(Integer)
    purchases = relationship("Purchase", back_populates="business")

class UserBusiness(Base):
    __tablename__ = 'user_business'
    user_id = Column(Integer, ForeignKey('users.id'), primary_key=True)
    business_id = Column(Integer, ForeignKey('businesses.id'), primary_key=True)
    points = Column(Integer, default=0)
    user = relationship("User", back_populates="businesses")
    business = relationship("Business")

class Purchase(Base):
    __tablename__ = 'purchases'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    business_id = Column(Integer, ForeignKey('businesses.id'))
    amount = Column(Float)
    points_used = Column(Integer, default=0)
    timestamp = Column(DateTime, default=datetime.utcnow)
    business = relationship("Business", back_populates="purchases")

# Инициализация БД
engine = create_engine('sqlite:///database.db')
Session = sessionmaker(bind=engine)
Base.metadata.create_all(engine)