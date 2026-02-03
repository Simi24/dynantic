"""
AWS DynamoDB Movies Table Example

Following the official AWS DynamoDB Getting Started guide:
https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/GettingStartedDynamoDB.html
"""

from typing import Any

from dynantic import Attr, DynamoModel, Key, SortKey


class Movie(DynamoModel):
    """Movie model with composite key (year + title)"""

    year: int = Key()
    title: str = SortKey()
    plot: str
    rating: float
    actors: list[str] | None = None
    genres: set[str] | None = None
    info: dict[str, Any] | None = None

    class Meta:
        table_name = "Movies"


# Create movies
movie1 = Movie(
    year=2013,
    title="Rush",
    plot="A re-creation of the 1970s rivalry between Formula One rivals.",
    rating=8.1,
    actors=["Daniel Brühl", "Chris Hemsworth", "Olivia Wilde"],
    genres={"Biography", "Drama", "Sport"},
)
movie1.save()

movie2 = Movie(
    year=2013,
    title="Prisoners",
    plot="When Keller Dover's daughter goes missing, he takes matters into his own hands.",
    rating=8.1,
    actors=["Hugh Jackman", "Jake Gyllenhaal", "Viola Davis"],
    genres={"Crime", "Drama", "Mystery"},
    info={"director": "Denis Villeneuve", "runtime_minutes": 153},
)
movie2.save()

# Get a movie
movie = Movie.get(2013, "Rush")
if movie:
    print(f"Found: {movie.title} ({movie.year}) - {movie.rating}/10")

# Query movies by year
movies_2013 = Movie.query(2013).all()
print(f"\nMovies from 2013: {len(movies_2013)}")
for m in movies_2013:
    print(f"  - {m.title}: {m.rating}/10")

# Query with sort key condition
movies_starting_with_p = Movie.query(2013).starts_with("P").all()
print(f"\n2013 movies starting with 'P': {[m.title for m in movies_starting_with_p]}")

# Atomic update (no fetch required)
Movie.update(2013, "Rush").set(Movie.rating, 8.3).execute()
print("\nUpdated Rush rating to 8.3")

# Conditional save (create-if-not-exists)
new_movie = Movie(
    year=2013,
    title="Gravity",
    plot="Two astronauts work together to survive after an accident.",
    rating=7.7,
    actors=["Sandra Bullock", "George Clooney"],
    genres={"Drama", "Sci-Fi", "Thriller"},
)
try:
    new_movie.save(condition=Attr("year").not_exists())
    print("Saved Gravity")
except Exception:
    print("Gravity already exists")

# Delete
Movie.delete(2013, "Gravity")
print("Deleted Gravity")

# Filter query results on non-key attributes
print("\n=== Filter Examples ===")

# Query 2013 movies with high ratings
high_rated_2013 = Movie.query(2013).filter(Attr("rating") >= 8.0).all()
print(f"\n2013 movies rated >= 8.0: {[m.title for m in high_rated_2013]}")

# Query with multiple filters (AND)
thriller_dramas = (
    Movie.query(2013).filter(Attr("genres").contains("Drama")).filter(Attr("rating") >= 8.0).all()
)
print(f"2013 Drama movies rated >= 8.0: {[m.title for m in thriller_dramas]}")

# Complex filter with OR condition
condition = (Attr("rating") >= 8.5) | Attr("genres").contains("Sci-Fi")
sci_fi_or_excellent = Movie.query(2013).filter(condition).all()
print(f"2013 Sci-Fi OR highly rated: {[m.title for m in sci_fi_or_excellent]}")

# Scan with filter (searches entire table)
all_dramas = Movie.scan().filter(Attr("genres").contains("Drama")).limit(10).all()
print(f"\nAll Drama movies (limit 10): {len(all_dramas)}")

# Scan all movies
all_movies = list(Movie.scan().limit(10))
print(f"\nTotal movies scanned: {len(all_movies)}")
