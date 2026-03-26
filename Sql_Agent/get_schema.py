import sqlite3

# def extract_schema(db_path):
#     conn = sqlite3.connect(db_path)
#     cursor = conn.cursor()

#     cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
#     tables = cursor.fetchall()

#     schema = {}

#     for table_name in tables:
#         table_name = table_name[0]
#         cursor.execute(f"PRAGMA table_info({table_name});")
#         columns = cursor.fetchall()
#         schema[table_name] = [col[1] for col in columns]

#     return schema


from sqlalchemy import create_engine, inspect

def extract_schema(connection_uri: str):
    """
    Extracts a full relational schema using SQLAlchemy.
    Works for SQLite, PostgreSQL, MySQL, etc.
    """
    engine = create_engine(connection_uri)
    inspector = inspect(engine)
    
    schema_lines = ["Tables:"]
    foreign_key_lines = []

    # Iterate through all tables in the database
    for table_name in inspector.get_table_names():
        # 1. Extract Columns and Primary Keys
        columns = inspector.get_columns(table_name)
        column_defs = []
        primary_keys = []

        for col in columns:
            name = col['name']
            col_type = str(col['type'])
            column_defs.append(f"{name} {col_type}")
            
            # SQLAlchemy returns primary_key as a boolean or 1/0
            if col.get('primary_key'):
                primary_keys.append(name)

        # Format the table line: - table_name(col1 TYPE, col2 TYPE) | PK: (col1)
        table_line = f"- {table_name}({', '.join(column_defs)})"
        if primary_keys:
            table_line += f" | Primary Key: ({', '.join(primary_keys)})"
        
        schema_lines.append(table_line)

        # 2. Extract Foreign Keys
        fks = inspector.get_foreign_keys(table_name)
        for fk in fks:
            referred_table = fk['referred_table']
            # fks can be composite, so we zip constrained and referred columns
            for from_col, to_col in zip(fk['constrained_columns'], fk['referred_columns']):
                foreign_key_lines.append(f"- {table_name}.{from_col} → {referred_table}.{to_col}")

    # Append Foreign Keys section if any exist
    if foreign_key_lines:
        schema_lines.append("\nForeign Keys:")
        schema_lines.extend(foreign_key_lines)

    return "\n".join(schema_lines)

# schema = extract_schema("database\\flight_1\\flight_1.sqlite")
# print(schema)