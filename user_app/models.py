# models.py
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean, Text, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from enum import Enum as PyEnum
from base import Base  # Импортируем Base из отдельного файла

# Стандартные уровни (если бизнес не создает свои)
class DefaultLevel(PyEnum):
    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"

class LoyaltyLevel(Base):
    __tablename__ = 'loyalty_levels'
    
    id = Column(Integer, primary_key=True)
    business_id = Column(Integer, ForeignKey('businesses.id'), nullable=True)
    name = Column(String(50), nullable=False)
    min_points = Column(Integer, default=0)
    rewards = Column(JSON)
    is_default = Column(Boolean, default=False)
    
    # Связь с Business
    business = relationship("Business", back_populates="levels")

class Promotion(Base):
    __tablename__ = 'promotions'
    
    id = Column(Integer, primary_key=True)
    business_id = Column(Integer, ForeignKey('businesses.id'))
    title = Column(String(100), nullable=False)
    description = Column(Text)
    start_date = Column(DateTime, nullable=False)
    end_date = Column(DateTime, nullable=False)
    is_active = Column(Boolean, default=True)
    
    # Связь с Business
    business = relationship("Business", back_populates="promotions")

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    full_name = Column(String(150))
    username = Column(String(50))
    registration_date = Column(DateTime, default=datetime.utcnow)
    
    # Связи
    businesses = relationship("UserBusiness", back_populates="user")
    purchases = relationship("Purchase", back_populates="user")

    @property
    def business_info(self):
        return [
            {
                "business": ub.business.name,
                "points": ub.points,
                "level": ub.level.name if ub.level else None
            } for ub in self.businesses
        ]

class Business(Base):
    __tablename__ = 'businesses'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    conversion_rate = Column(Float, default=10.0)
    point_value = Column(Float, default=1.0)
    admin_id = Column(Integer, nullable=False)
    
    # Связи
    levels = relationship("LoyaltyLevel", back_populates="business")
    promotions = relationship("Promotion", back_populates="business")
    clients = relationship("UserBusiness", back_populates="business")
    purchases = relationship("Purchase", back_populates="business")

class UserBusiness(Base):
    __tablename__ = 'user_business'
    
    user_id = Column(Integer, ForeignKey('users.id'), primary_key=True)
    business_id = Column(Integer, ForeignKey('businesses.id'), primary_key=True)
    points = Column(Integer, default=0)
    level_id = Column(Integer, ForeignKey('loyalty_levels.id'))
    
    # Связи
    user = relationship("User", back_populates="businesses")
    business = relationship("Business", back_populates="clients")
    level = relationship("LoyaltyLevel")

    def update_level(self):
        """Обновление уровня с учетом кастомных или стандартных правил"""
        levels = (
            self.business.levels 
            if self.business.levels 
            else self._get_default_levels()
        )
        sorted_levels = sorted(levels, key=lambda x: x.min_points, reverse=True)
        for lvl in sorted_levels:
            if self.points >= lvl.min_points:
                self.level = lvl
                break

    def _get_default_levels(self):
        return [
            LoyaltyLevel(name=DefaultLevel.GOLD.value, min_points=1000),
            LoyaltyLevel(name=DefaultLevel.SILVER.value, min_points=500),
            LoyaltyLevel(name=DefaultLevel.BRONZE.value, min_points=0)
        ]

class Purchase(Base):
    __tablename__ = 'purchases'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    business_id = Column(Integer, ForeignKey('businesses.id'))
    amount = Column(Float)
    amount_paid = Column(Float)
    points_used = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Связи
    user = relationship("User", back_populates="purchases")
    business = relationship("Business", back_populates="purchases")

    def calculate_payment(self):
        points_value = self.business.point_value
        self.amount_paid = max(self.amount - (self.points_used * points_value), 0)
