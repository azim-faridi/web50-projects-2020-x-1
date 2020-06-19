import os, json

from flask import Flask, session, redirect, render_template, request, jsonify, flash
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from datetime import datetime

from werkzeug.security import check_password_hash, generate_password_hash

import requests

from helpers import login_required

app = Flask(__name__)
app.config['SECRET_KEY'] = 'random'

if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

engine = create_engine(os.getenv("DATABASE_URL"))

db = scoped_session(sessionmaker(bind=engine))


@app.route("/")
@login_required
def index():

    return render_template("index.html")

@app.route("/login", methods=["GET", "POST"])
def login():

    session.clear()

    username = request.form.get("username")

    if request.method == "POST":

        if not request.form.get("username"):
            return render_template("error.html", message="please provide valid username")

        elif not request.form.get("password"):
            return render_template("error.html", message="need password to login")

        rows = db.execute("SELECT * FROM users WHERE username = :username",
                            {"username": username})
        
        result = rows.fetchone()

        if result == None or not check_password_hash(result[2], request.form.get("password")):
            return render_template("error.html", message="invalid username and/or password")

        session["user_id"] = result[0]
        session["user_name"] = result[1]

        return redirect("/")

    else:
        return render_template("login.html")

@app.route("/logout")
def logout():

    session.clear()

    return render_template("logout.html", message="please visit back soon!")

@app.route("/register", methods=["GET", "POST"])
def register():
    
    session.clear()
    
    if request.method == "POST":

        if not request.form.get("username"):
            return render_template("error.html", message="please provide username")

        userCheck = db.execute("SELECT * FROM users WHERE username = :username",
                          {"username":request.form.get("username")}).fetchone()

        if userCheck:
            return render_template("error.html", message="username already exist")

        elif not request.form.get("password"):
            return render_template("error.html", message="please provide password")

   
        elif not request.form.get("confirmation"):
            return render_template("error.html", message="please confirm password")

        elif not request.form.get("password") == request.form.get("confirmation"):
            return render_template("error.html", message="passwords didn't match")
        
        hashedPassword = generate_password_hash(request.form.get("password"), method='pbkdf2:sha256', salt_length=8)
        
      
        db.execute("INSERT INTO users (username, hash) VALUES (:username, :password)",
                            {"username":request.form.get("username"), 
                             "password":hashedPassword})

        db.commit()

        return render_template("success.html", message="Account created.")

        return redirect("/login")

    else:
        return render_template("register.html")

@app.route("/search", methods=["GET"])
@login_required
def search():
   
    if not request.args.get("book"):
        return render_template("error.html", message="Please provide valid book in order to search for you.")

    query = "%" + request.args.get("book") + "%"

    query = query.title()
    
    rows = db.execute("SELECT isbn, title, author, year FROM books WHERE \
                        isbn LIKE :query OR \
                        title LIKE :query OR \
                        author LIKE :query LIMIT 15",
                        {"query": query})
    
    if rows.rowcount == 0:
        return render_template("error.html", message="we can't find books with that description.")
    
    books = rows.fetchall()

    return render_template("results.html", books=books)

@app.route("/book/<isbn>", methods=["GET","POST"])
@login_required
def book(isbn):

    if request.method == "POST":

        currentUser = session["user_id"]
        
        rating = request.form.get("rating")
        comment = request.form.get("comment")
        
        row = db.execute("SELECT book_id FROM books WHERE isbn = :isbn",
                        {"isbn": isbn})


        bookId = row.fetchone() 
        bookId = bookId[0]

        row2 = db.execute("SELECT * FROM reviews WHERE user_id = :user_id AND book_id = :book_id",
                    {"user_id": currentUser,
                     "book_id": bookId})

        if row2.rowcount == 1:
            
            return render_template("error.html", message="Review already submitted, you are not allowed to review the same book twice.")

            return redirect("/book/" + isbn)

        rating = int(rating)

        db.execute("INSERT INTO reviews (user_id, book_id, comment, rating, time) VALUES \
                    (:user_id, :book_id, :comment, :rating, :time)",
                    {"user_id": currentUser, 
                    "book_id": bookId, 
                    "comment": comment, 
                    "rating": rating,
                    "time": time})
       
        db.commit()

        return render_template("success.html", message="Review submitted.")

    else:

        row = db.execute("SELECT isbn, title, author, year FROM books WHERE \
                        isbn = :isbn",
                        {"isbn": isbn})

        bookInfo = row.fetchall()

        key = os.getenv("StdHUV8pFW4g3wvpynp9Q")
        
        query = requests.get("https://www.goodreads.com/book/review_counts.json",
                params={"key": key, "isbns": isbn})

        response = query.json()

        response = response['books'][0]

        bookInfo.append(response)

        row = db.execute("SELECT book_id FROM books WHERE isbn = :isbn",
                        {"isbn": isbn})

        
        book = row.fetchone()
        book = book[0]

        results = db.execute("SELECT reviews.user_id, reviews.comment, reviews.rating, reviews.time  FROM reviews INNER JOIN users ON reviews.user_id = users.user_id WHERE book_id = :book",
                            {"book": book})

        reviews = results.fetchall()

        return render_template("book.html", bookInfo=bookInfo, reviews=reviews)


@app.route("/api/<isbn>")
def api(isbn):
    goodreads_api_key = "StdHUV8pFW4g3wvpynp9Q"
    url = f"https://www.goodreads.com/book/review_counts.json?key={goodreads_api_key}&isbns={isbn}"
    response = requests.get(url)
    # TEST isbn: 0441172717

    if (response.status_code == 200):
        response = response.json()
        review_count = response["books"][0]["reviews_count"]
        average_score = response["books"][0]["average_rating"]
        try:
            (title, author, year) = db.execute("""SELECT title, author, year FROM "books" WHERE isbn=:isbn""", {"isbn":isbn}).fetchone()
        except:
            return jsonify({"error": "Book not found."})

        result = {
            "title": title,
            "author": author,
            "year": str(year),
            "isbn": isbn,
            "review_count": str(review_count),
            "average_score": str(average_score)
        }
        return jsonify(result)
    else:
        error = "Server did not respond correctly."
        flash(error)
        return redirect("/search")
