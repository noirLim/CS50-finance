import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    # query user portfolio by user id
    portfolio = db.execute(
        "SELECT id, symbol, SUM(shares)  FROM trades WHERE id = ? GROUP BY symbol HAVING SUM(shares) > 0 ORDER BY price DESC", session["user_id"])
    
    user_cash = db.execute("SELECT * FROM users WHERE id = ?", session["user_id"])

    current_worth = 0
    # update user_portfolio with stock current price and total actual price of shares
    for stock in portfolio:
        stock_data = lookup(stock["symbol"])
        stock["currentprice"] = stock_data["price"]
        stock["totalprice"] = stock_data["price"] * stock["SUM(shares)"]
        current_worth += stock["totalprice"]

    
    return render_template("index.html",portfolio=portfolio,user_cash=user_cash,current_worth=current_worth)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    if request.method == "GET":
        return render_template("buy.html")
    else:
        symbol = request.form["symbol"]
        shares = request.form["shares"]
        
        # check if field is empty
        if symbol == "" or shares == "":
            return apology("symbol or shares cannot be empty")
        # check if shares is numeric
        elif not shares.isnumeric():
            return apology("fractional not supported", 400)
        # check if shares not below or equal to zero
        elif int(shares) <= 0:
            return apology("share number can't be negative number or zero!")
        
        stock = lookup(symbol)

        if not stock:
            return apology("INVALID SYMBOL", 400)
        else:
            total_cost = int(shares) * stock["price"]
            user_cash = db.execute("SELECT * FROM users WHERE id = ?", session["user_id"])
            # check user cash if afford to buy
            if user_cash[0]["cash"] < total_cost:
                return apology("Cannot Buy", 400)
            else:
                db.execute("INSERT INTO trades (id, symbol, shares, price) VALUES(?, ?, ?, ?)",
                       session["user_id"], stock['symbol'], int(shares), stock['price'])
                cash = user_cash[0]["cash"]
                # update user cash by user id
                db.execute("UPDATE users SET cash = ? WHERE id = ?", cash - total_cost, session["user_id"])
                flash('Bought!')
                return redirect("/")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    user_transactions = db.execute(
        "SELECT id, symbol, shares, price, transacted  FROM trades WHERE id = ? ORDER BY transacted", session["user_id"])

    return render_template("history.html", user_transactions=user_transactions)



@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":
        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute(
            "SELECT * FROM users WHERE username = ?", request.form.get("username")
        )

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(
            rows[0]["hash"], request.form.get("password")
        ):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "GET":
        return render_template("quote.html")
    else:
        symbol = request.form["symbol"]
        
        if symbol == "":
            return apology("Input is blank")
        
        stock = lookup(symbol)
        
        if stock != None:
            return render_template("quoted.html",symbol=stock)
        else:
            return apology("Invalid Symbol")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    # remove all user_id
    session.clear()

    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        confirmation = request.form["confirmation"]

        rows = db.execute("SELECT * FROM users WHERE username = ?", username)
        
        # check if contain blank field
        if username == '' or password == '' or confirmation == '':
            return apology("Field cannot be empty")
        
        # check if password and confirmation is match
        elif password != confirmation:
            return apology("Password do not match")
        
        # check if users is exists
        elif len(rows) == 1:
            return apology("username already exist", 400)
        
        else:
            hash_pass = generate_password_hash(password)
            db.execute("INSERT INTO users (username, hash) VALUES(?, ?)", username, hash_pass)
            return redirect('/')

    return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    if request.method == "POST":
        symbol = request.form.get("symbol")
        shares= request.form.get("shares")
        
        if symbol == None or shares == None or symbol == "" or shares == "":
            print("symbol or shares is invalid")
        elif int(shares) <= 0:
            print("Shares cannot negative or zero")
        
        # lookup stock 
        stock = lookup(symbol)

        if stock == None:
            return apology("Invalid symbol", 400)
        
        user_portfolio = db.execute(
            "SELECT id, symbol, SUM(shares) FROM trades WHERE id = ? AND symbol = ? GROUP BY symbol HAVING SUM(shares)>0 ", session["user_id"], stock['symbol'])
        user_cash = db.execute("SELECT * FROM users WHERE id = ?", session["user_id"])

        if user_portfolio[0]["SUM(shares)"] < int(shares):
            return apology("too many shares")
        else:
            # update user_portfolio with based on sell transaction info
            currentprice = stock['price'] * int(shares)
            cash = user_cash[0]["cash"]
            db.execute("UPDATE users SET cash = ? WHERE id = ?", cash + currentprice, session["user_id"])
            db.execute("INSERT INTO trades (id, symbol, shares, price) VALUES(?, ?, ?, ?)",
                       session["user_id"], stock['symbol'], -int(shares), stock['price'])
            flash(f'{stock["symbol"]} sold')
        return redirect("/")

    else:
         portfolio = db.execute(
         "SELECT id, symbol, SUM(shares)  FROM trades WHERE id = ? GROUP BY symbol HAVING SUM(shares) > 0 ORDER BY price DESC", session["user_id"])
         return render_template("sell.html",portfolio=portfolio)
    
# change user password
@app.route("/settings",methods=["GET","POST"])
@login_required
def settings():
    if request.method == "POST":
        old_password = request.form["old_password"]
        new_password = request.form["new_password"]
         
        rows = db.execute(
            "SELECT * FROM users WHERE id = ?",session["user_id"]
        )

        # check if field is empty
        if old_password == "" or new_password == "":
            return apology("Field cannot be empty")
        # check if old_password match with database
        elif not check_password_hash(rows[0]["hash"],old_password):
            return apology("Wrong old password")
        # check if old_password not match with new password
        elif old_password != new_password:
             db.execute("UPDATE users SET hash = ? WHERE id = ?",generate_password_hash(new_password) , session["user_id"])
             flash(f'Password Changed!')
             return redirect('/')
    else:
        return render_template("settings.html")
     
