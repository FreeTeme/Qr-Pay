from models import Session, User, Business, UserBusiness, Purchase

def get_user(tg_id: int):
    session = Session()
    user = session.query(User).filter_by(telegram_id=tg_id).first()
    session.close()
    return user

def create_user(user_data: dict):
    session = Session()
    user = User(
        telegram_id=user_data['id'],
        full_name=user_data.get('full_name'),
        username=user_data.get('username'),
        gender=user_data.get('gender'),
        email=user_data.get('email'),
        birth_date=user_data.get('birth_date')
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    session.close()
    return user

def get_business(business_id: int):
    session = Session()
    business = session.query(Business).get(business_id)
    session.close()
    return business

# ... Аналогичные методы для других операций ...