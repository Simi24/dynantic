"""
Example demonstrating filter support on queries and scans.

This shows how to use PynamoDB-style filtering on non-primary key fields
for both query and scan operations.

NOTE: Examples use Attr() for mypy compatibility. The metaclass DSL (Movie.rating >= 8.0)
works at runtime but mypy doesn't understand it. Use Attr("field") for type-safe code.
"""

from dynantic import Attr, DynamoModel, Key, SortKey


class Movie(DynamoModel):
    """Movie model with composite key (year + title)"""

    year: int = Key()
    title: str = SortKey()
    plot: str
    rating: float
    actors: list[str] | None = None
    genres: set[str] | None = None

    class Meta:
        table_name = "Movies"


# Create test data
print("Creating test movies...")
movies_data = [
    Movie(
        year=2013,
        title="Rush",
        plot="A re-creation of the 1970s rivalry between Formula One rivals.",
        rating=8.1,
        actors=["Daniel Brühl", "Chris Hemsworth", "Olivia Wilde"],
        genres={"Biography", "Drama", "Sport"},
    ),
    Movie(
        year=2013,
        title="Prisoners",
        plot="When Keller Dover's daughter goes missing...",
        rating=8.1,
        actors=["Hugh Jackman", "Jake Gyllenhaal", "Viola Davis"],
        genres={"Crime", "Drama", "Mystery"},
    ),
    Movie(
        year=2013,
        title="Gravity",
        plot="Two astronauts work together to survive after an accident.",
        rating=7.7,
        actors=["Sandra Bullock", "George Clooney"],
        genres={"Drama", "Sci-Fi", "Thriller"},
    ),
    Movie(
        year=2014,
        title="Interstellar",
        plot="A team of explorers travel through a wormhole in space...",
        rating=8.6,
        actors=["Matthew McConaughey", "Anne Hathaway", "Jessica Chastain"],
        genres={"Drama", "Sci-Fi", "Adventure"},
    ),
    Movie(
        year=2014,
        title="Whiplash",
        plot="A promising young drummer enrolls at a cut-throat music conservatory...",
        rating=8.5,
        actors=["Miles Teller", "J.K. Simmons"],
        genres={"Drama", "Music"},
    ),
]

for movie in movies_data:
    movie.save()

print(f"Created {len(movies_data)} movies\n")

# ============================================================================
# QUERY WITH FILTERS
# ============================================================================

print("=" * 80)
print("QUERY WITH FILTERS")
print("=" * 80)

# Query with single filter on non-key field
print("\n1. Query 2013 movies with rating >= 8.0:")
high_rated_2013 = Movie.query(2013).filter(Attr("rating") >= 8.0).all()
for movie in high_rated_2013:
    print(f"   - {movie.title}: {movie.rating}/10")

# Query with multiple filters (AND)
print("\n2. Query 2013 movies with rating >= 8.0 AND Drama genre:")
drama_high_rated = (
    Movie.query(2013).filter(Attr("rating") >= 8.0).filter(Attr("genres").contains("Drama")).all()
)
for movie in drama_high_rated:
    print(f"   - {movie.title}: {movie.rating}/10, Genres: {movie.genres}")

# Query with complex condition (OR)
print("\n3. Query 2013 movies that are high rated OR have Sci-Fi genre:")
condition = (Attr("rating") >= 8.0) | (Attr("genres").contains("Sci-Fi"))
scifi_or_high = Movie.query(2013).filter(condition).all()
for movie in scifi_or_high:
    print(f"   - {movie.title}: {movie.rating}/10, Genres: {movie.genres}")

# Query with filter combining key condition and filter
print("\n4. Query 2013 movies starting with 'P' and rating < 8.5:")
p_movies = Movie.query(2013).starts_with("P").filter(Attr("rating") < 8.5).all()
for movie in p_movies:
    print(f"   - {movie.title}: {movie.rating}/10")

# ============================================================================
# SCAN WITH FILTERS
# ============================================================================

print("\n" + "=" * 80)
print("SCAN WITH FILTERS")
print("=" * 80)

# Scan with single filter
print("\n5. Scan all movies with rating >= 8.5:")
excellent_movies = Movie.scan().filter(Attr("rating") >= 8.5).all()
for movie in excellent_movies:
    print(f"   - {movie.title} ({movie.year}): {movie.rating}/10")

# Scan with multiple filters
print("\n6. Scan Drama movies with rating between 8.0 and 8.5:")
good_dramas = (
    Movie.scan()
    .filter(Attr("genres").contains("Drama"))
    .filter(Attr("rating").between(8.0, 8.5))
    .all()
)
for movie in good_dramas:
    print(f"   - {movie.title} ({movie.year}): {movie.rating}/10")

# Scan with complex condition
print("\n7. Scan Sci-Fi OR high rated (>= 8.5) movies:")
complex_condition = (Attr("genres").contains("Sci-Fi")) | (Attr("rating") >= 8.5)
scifi_or_excellent = Movie.scan().filter(complex_condition).all()
for movie in scifi_or_excellent:
    print(f"   - {movie.title} ({movie.year}): {movie.rating}/10, Genres: {movie.genres}")

# Scan with limit
print("\n8. Scan top 3 movies (with limit):")
top_movies = Movie.scan().filter(Attr("rating") >= 7.5).limit(3).all()
for movie in top_movies:
    print(f"   - {movie.title} ({movie.year}): {movie.rating}/10")

# ============================================================================
# FILTER WITH VARIOUS OPERATORS
# ============================================================================

print("\n" + "=" * 80)
print("VARIOUS FILTER OPERATORS")
print("=" * 80)

# Greater than
print("\n9. Movies with rating > 8.0:")
gt_movies = Movie.scan().filter(Attr("rating") > 8.0).all()
print(f"   Found {len(gt_movies)} movies")

# Less than or equal
print("\n10. Movies with rating <= 8.0:")
lte_movies = Movie.scan().filter(Attr("rating") <= 8.0).all()
print(f"   Found {len(lte_movies)} movies")

# Equals
print("\n11. Movies with rating exactly 8.1:")
exact_movies = Movie.scan().filter(Attr("rating") == 8.1).all()
for movie in exact_movies:
    print(f"   - {movie.title}: {movie.rating}/10")

# Contains (for sets/lists/strings)
print("\n12. Movies with 'Sci-Fi' genre:")
scifi_movies = Movie.scan().filter(Attr("genres").contains("Sci-Fi")).all()
for movie in scifi_movies:
    print(f"   - {movie.title}: {movie.genres}")

# Between
print("\n13. Movies from years 2013-2014:")
year_range = Movie.scan().filter(Attr("year").between(2013, 2014)).all()
print(f"   Found {len(year_range)} movies")

# Begins with (for strings)
print("\n14. Movies with title starting with 'I':")
i_movies = Movie.scan().filter(Attr("title").begins_with("I")).all()
for movie in i_movies:
    print(f"   - {movie.title}")

# Combined with AND and OR
print("\n15. Movies that are (Drama AND rating > 8.0) OR Sci-Fi:")
combined = (
    Movie.scan()
    .filter(
        ((Attr("genres").contains("Drama")) & (Attr("rating") > 8.0))
        | (Attr("genres").contains("Sci-Fi"))
    )
    .all()
)
for movie in combined:
    print(f"   - {movie.title}: {movie.rating}/10, Genres: {movie.genres}")

print("\n" + "=" * 80)
print("Filter examples completed!")
print("=" * 80)
