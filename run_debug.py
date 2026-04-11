from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, DateTime, create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
from flaskteroids.model import Model, validates, init
from flaskteroids import registry
from flaskteroids.rules import rules

Base = declarative_base()

class ProductBase(Base):
    __tablename__ = 'products'
    id = Column(Integer(), primary_key=True, autoincrement=True)
    quantity = Column(Integer())
    created_at = Column(DateTime())
    updated_at = Column(DateTime())
    expires_at = Column(DateTime())

@rules(
    validates('quantity', comparison={'greater_than': 10}),
)
class Product(Model):
    pass

engine = create_engine('sqlite:///:memory:')
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

# patch model.session
import flaskteroids.model as mod
mod.session = Session()

# register model in registry
registry.get(Model)['models'] = {'Product': Product}
registry.get(Product)['base_class'] = ProductBase
init(Product)

p = Product.new(quantity=20)
print('p._changes:', p._changes)
print('getattr p.quantity:', getattr(p, 'quantity'))
print('validates:', registry.get(Product).get('validates'))
# run validation logic directly
errs = []
for vr in registry.get(Product).get('validates'):
    errs.extend(vr(instance=p))
print('errs:', errs)
print('save result:', p.save())
print('errors count:', p.errors.count)
print('errors full:', p.errors.full_messages())
