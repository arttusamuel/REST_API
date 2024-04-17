from fastapi import FastAPI, HTTPException, Request, status, Depends

from typing import Annotated # to annotate session dependency
from pydantic import BaseModel, Field # only for ORM use? and data validation
import database
from database import engine, SessionLocal, get_table_length
from sqlalchemy.orm import Session
from dotenv import load_dotenv
from fetch_api_data import fetch_api_data
import models


load_dotenv()

##################
app = FastAPI()


# This try-clause ought to be better placed
try:
    database.Base.metadata.create_all(bind=engine)
    print("Creating all tables from models to database")
except Exception as e:
    print("Error: ", e)

# Database dependency method
def get_db():
    print("Creating session in get_db()")
    db = SessionLocal()
    db.__init__
    try:
        yield db
    finally:
        db.close()

# Checks the amout of models.Stock -type items in database and returns next value as int
def generate_id(db: Session) -> int:
    # Query the length of the Stock table
    table_length = db.query(models.Stock).count()
    # Generate ID based on the length of the table
    return table_length + 1

db_dependency = Annotated[Session, Depends(get_db)]



######################    
# FastAPI endpoints  to PORTFOLIO
# Endpoint to populate the database
@app.post("/populate_database")
def populate_database(db: Session = Depends(get_db)):
    try:
        stock_data_list = fetch_api_data()
        for stock_data in stock_data_list:
            stock = models.Stock(**stock_data) #be sure of stock_data model
            db.add(stock)
        db.commit()
        return {"added stockdata"}

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    

# Post toimii 
@app.post("/stock/")
def create_stock(stock: models.StockBase, db: Session = Depends(get_db)):
    try:
        print("Trying to post("")")
        db_stock = models.Stock(**stock.model_dump())
        db.add(db_stock)
        db.commit()
        db.refresh(db_stock)
        return db_stock
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/stock/")
def get_stock(db: Session = Depends(get_db)):
    
    stock_data = db.query(models.Stock).all()
    if not stock_data:
        raise HTTPException(status_code=404, detail="Stock_data not found")
    return stock_data

@app.get("/stock/{stock_id}")
def get_stock(stock_id: int, db: Session = Depends(get_db)):
    stock = db.query(models.Stock).filter(models.Stock.id == stock_id).first()
    
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")
    return stock

@app.put("//{id}/update-volume/")
async def update_volume(id: int, volume: int, db: Session = Depends(get_db)):
    stock = db.query(models.Stock).filter(models.Stock.id == id).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")
    stock.volume = volume
    db.commit()
    db.refresh(stock)
    return {"message": "Volume updated successfully", "ticker": id, "new_volume": volume}


# Portfolio calls
@app.post("/portfolio/post")
async def create_portfolio_item(stocks: str, value: int, Session = Depends(get_db)):
    new_portfolio_item = models.Portfolio(stocks=stocks, value=value)
    Session.add(new_portfolio_item)
    Session.commit()
    return new_portfolio_item

@app.get("/Get/All")
async def get_portfolio(db: Session = Depends(get_db)): 
    portfolio = db.query(models.Portfolio).all()
    return portfolio

@app.put("/portfolio/{id}")
async def update_portfolio_item(session, portfolio_id: int, stocks: str, value: int):
    portfolio_item = session.query(models.Portfolio).filter(models.Portfolio.id == portfolio_id).first()
    if portfolio_item:
        portfolio_item.stocks = stocks
        portfolio_item.value = value
        session.commit()
        return portfolio_item
    else:
        return None  # Portfolio item not found
