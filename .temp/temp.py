import pandas as pd
import duckdb

# Read the data into a Pandas DataFrame
data = {
    "Identifier": [206, 216, 218, 472, 480],
    "Place of Publication": ["London", "London; Virtue & Yorston", "London", "London", "London"],
    "Date of Publication": ["1879 [1878]", "1868", "1869", "1851", "1857"],
    "Publisher": ["S. Tinsley & Co.", "Virtue & Co.", "Bradbury, Evans & Co.", "James Darling", "Wertheim & Macintosh"],
    "Title": ["Walter Forbes. [A novel.] By A. A", "All for Greed. [A novel. The dedication signed... A., A. A.", "Love the Avenger. By the author of “All for Gr... A., A. A.", "Welsh Sketches, chiefly ecclesiastical, to the... A., E. S.", "[The World in which I live, and my place in it... A., E. S."],
    "Author": ["A. A.", "A., A. A.", "A., A. A.", "A., E. S.", "A., E. S."],
    "Flickr URL": ["http://www.flickr.com/photos/britishlibrary/ta...", "http://www.flickr.com/photos/britishlibrary/ta...", "http://www.flickr.com/photos/britishlibrary/ta...", "http://www.flickr.com/photos/britishlibrary/ta...", "http://www.flickr.com/photos/britishlibrary/ta..."],
    "Place of Publication_1": [None, None, None, None, None]
}
df = pd.DataFrame(data)

# Create a DuckDB connection
con = duckdb.connect()

# Register the DataFrame as a DuckDB table
con.register("df", df)

# Use DuckDB to convert the column
# query = """
#     SELECT *,
#         CASE
#             WHEN "Place of Publication" LIKE '%London%' THEN 'London'
#             WHEN "Place of Publication" LIKE '%Oxford%' THEN 'Oxford'
#             ELSE REPLACE("Place of Publication", '-', ' ')
#         END as "Place of Publication"
#     FROM df
# """
query = """
   UPDATE df
    SET "Place of Publication" = 
        CASE
            WHEN "Place of Publication" LIKE '%London%' THEN 'London'
            WHEN "Place of Publication" LIKE '%Oxford%' THEN 'Oxford'
            ELSE REPLACE("Place of Publication", '-', ' ') 
        END;
"""


# Execute the query and print the output
output = con.execute(query).fetchdf()
