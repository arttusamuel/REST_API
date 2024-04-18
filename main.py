from fastapi import FastAPI, HTTPException, Request, status, Depends

from typing import Annotated # to annotate session dependency
from pydantic import BaseModel, Field # only for ORM use? and data validation
import database
from database import engine, SessionLocal, get_table_length
from sqlalchemy.orm import Session
from dotenv import load_dotenv
import models
from fastapi.middleware.cors import CORSMiddleware

import datetime

import requests
import json
import os

load_dotenv()

##################
app = FastAPI()
TOK_API_TOKEN = os.getenv("TOK_API_TOKEN")

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

# Fetching stock data from StockAPI and returning a list of stocks
def fetch_api_data() -> list:
    try:
        stock_tickers_list = ["AAPL,TSLA,MSFT"] #, "KO,NVDA,GOOG", "AMZN,LLY,JPM" <- lisää nämä kun tarvitaan enemmän tietoja
        stock_data_list = []
        table_length = get_table_length('stock')
        print("Length of 'stock_data' table:", table_length)

        for ticker in stock_tickers_list:
            url = f"https://api.stockdata.org/v1/data/quote?symbols={ticker}&api_token={TOK_API_TOKEN}"
            response = requests.get(url)

            if response.status_code == 200:
                quotes_data = json.loads(response.text)
                
                if 'data' in quotes_data:
                    stock_data = quotes_data['data']   
                    # Print out the fetched data
                    print(f"Fetched stock quotes for {len(stock_data)} stocks:")
                    today = datetime.date.today()
                    print(today)
                for stock in stock_data:
                        
                        stock_info = {
                            "id": table_length,
                            "ticker": stock['ticker'],
                            "name": stock['name'],
                            "price_today": stock['price'],
                            "volume": stock['volume'],
                            "last_days_price": stock['previous_close_price'],
                            "date": today
                        }
                        stock_data_list.append(stock_info)
                        table_length += 1  
        return stock_data_list
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
    today = datetime.date.today()
    print(today)
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
async def create_portfolio_item(portfolio_value: int, db: Session = Depends(get_db)):
    new_portfolio_item = models.Portfolio(portfolio_value=portfolio_value)
    db.add(new_portfolio_item)
    db.commit()
    return {"message": "new transaction done"}

@app.get("/portfolios/")
async def get_portfolios(db: Session = Depends(get_db)): 
    portfolios = db.query(models.Portfolio).all()
    return portfolios

@app.put("/portfolio/{id}")
async def update_portfolio_item(portfolio_id: int, portfolio_value: int, db: Session = Depends(get_db)):
    portfolio_item = db.query(models.Portfolio).filter(models.Portfolio.id == portfolio_id).first()
    if portfolio_item:
        portfolio_item.portfolio_value = portfolio_value
        db.commit()
        return portfolio_item
    else:
        raise HTTPException(status_code=404, detail="Portfolio item not found")

@app.delete("/portfolio/{id}")
async def delete_portfolio_item(portfolio_id: int, db: Session = Depends(get_db)):
    portfolio_item = db.query(models.Portfolio).filter(models.Portfolio.id == portfolio_id).first()
    if portfolio_item:
        db.delete(portfolio_item)
        db.commit()
        return {"message": "Portfolio item deleted successfully"}
    else:
        raise HTTPException(status_code=404, detail="Portfolio item not found")
#transaction
@app.post("/transactions/")
def create_transaction(stock_id: int, portfolio_id: int, stock_amount: int, db: Session = Depends(get_db)):
    # Check if stock and portfolio exist
    stock = db.query(models.Stock).filter(models.Stock.id == stock_id).first()
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")
    
    portfolio = db.query(models.Portfolio).filter(models.Portfolio.id == portfolio_id).first()
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    today = datetime.date.today()
    # Create a new transaction
    transaction = models.Transaction(stock_id=stock_id, portfolio_id=portfolio_id, stock_amount=stock_amount, purchase_date=today)
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return transaction
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Add the origin of your frontend
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)