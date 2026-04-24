# noinspection PyPackageRequirements
from faker import Faker
import psycopg2
import psycopg2.extensions
import psycopg2.pool
import time
import threading
import multiprocessing
import asyncio
import asyncpg


async def get_connection_async(n_coroutines):
    pool = await asyncpg.create_pool(
        user='postgres',
        password='SIQ3PAGDL8pa',
        host='192.168.111.15',
        port='5432',
        database='forgelab',
        min_size=n_coroutines,
        max_size=n_coroutines)
    return pool


async def insert_records_with_async(query, pool, values, n):
    async with pool.acquire() as connection:
        for _ in range(n):
            await connection.execute(query, *values)


async def run_insertions_with_async(n, n_coroutines):
    n_per_coroutine = n // n_coroutines
    query = "INSERT INTO customers (first_name, last_name, email, phone_number, address) VALUES ($1, $2, $3, $4, $5)"
    pool = await get_connection_async(n_coroutines)
    tasks = []
    values = generate_record()
    start = time.time()
    for _ in range(n_coroutines):
        task = asyncio.create_task(insert_records_with_async(query, pool, values, n_per_coroutine))
        tasks.append(task)
    await asyncio.gather(*tasks)
    end = time.time()
    print("Total time: ", end-start, "run_insertions_with_async")
    # Close the connection pool
    await pool.close()


def get_connection_pool(n_threads):
    connection_pool = psycopg2.pool.ThreadedConnectionPool(
        minconn=n_threads,
        maxconn=n_threads,
        user='postgres',
        password='SIQ3PAGDL8pa',
        host='192.168.111.15',
        port='5432',
        database='forgelab')
    return connection_pool


def insert_records_with_connection_pool(n, n_threads, connection_pool, query, values):
    conn = connection_pool.getconn()
    cursor = conn.cursor()
    for _ in range(n // n_threads):
        cursor.execute(query, values)
    connection_pool.putconn(conn)
    return


def create_records_with_multiprocessing_and_connections_inside_process(n, n_processor):
    query = "INSERT INTO customers (first_name, last_name, email, phone_number, address) VALUES (%s, %s, %s, %s, %s)"
    values = generate_record()
    # Create and start processes
    start = time.time()
    processes = []
    for _ in range(n_processor):
        n_per_thread = n // n_processor
        process = multiprocessing.Process(target=get_connection_and_insert_records, args=(n_per_thread, query, values))
        processes.append(process)
    # Wait for all processes to complete
    for process in processes:
        process.start()
    for process in processes:
        process.join()
    end = time.time()
    print("Total time: ", end - start, "create_records_with_multiprocessing_and_connections_inside_process")


def create_records_with_connection_pool(n, n_threads):
    connection_pool = get_connection_pool(n_threads)
    query = "INSERT INTO customers (first_name, last_name, email, phone_number, address) VALUES (%s, %s, %s, %s, %s)"
    values = generate_record()
    # Create and start threads
    start = time.time()
    threads = []
    for _ in range(n_threads):
        thread = threading.Thread(
            target=insert_records_with_connection_pool, args=(n, n_threads, connection_pool, query, values))
        threads.append(thread)
    # Wait for all threads to complete
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    end = time.time()
    print("Total time: ", end-start, "create_records_with_connection_pool")


def insert_records(n_per_thread, cursor, query, values):
    for _ in range(n_per_thread):
        cursor.execute(query, values)
    return


def create_records_with_threading(n, n_threads):
    conn, cursor = get_connection()

    query = "INSERT INTO customers (first_name, last_name, email, phone_number, address) VALUES (%s, %s, %s, %s, %s)"
    values = generate_record()
    # Create and start threads
    start = time.time()
    threads = []
    for _ in range(n_threads):
        n_per_thread = n // n_threads
        thread = threading.Thread(target=insert_records, args=(n_per_thread, cursor, query, values))
        threads.append(thread)
    # Wait for all threads to complete
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    end = time.time()
    print("Total time: ", end-start, "create_records_with_threading")
    conn.commit()

    cursor.close()
    conn.close()


def get_connection_and_insert_records(n_per_thread, query, values):
    conn, cursor = get_connection()
    for _ in range(n_per_thread):
        cursor.execute(query, values)

    conn.commit()
    cursor.close()
    conn.close()

    return


def create_records_with_threading_get_connection_inside_the_thread(n, n_threads):

    query = "INSERT INTO customers (first_name, last_name, email, phone_number, address) VALUES (%s, %s, %s, %s, %s)"
    values = generate_record()
    # Create and start threads
    start = time.time()
    threads = []
    for _ in range(n_threads):
        n_per_thread = n // n_threads
        thread = threading.Thread(target=get_connection_and_insert_records, args=(n_per_thread, query, values))
        threads.append(thread)
    # Wait for all threads to complete
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    end = time.time()
    print("Total time: ", end-start, "create_records_with_threading_get_connection_inside_the_thread")


def create_records_with_threading_and_n_connections(n, n_threads):

    connections = []
    for _ in range(n_threads):
        connections.append(get_connection())

    query = "INSERT INTO customers (first_name, last_name, email, phone_number, address) VALUES (%s, %s, %s, %s, %s)"
    values = generate_record()
    # Create and start threads
    start = time.time()
    threads = []
    for _i in range(n_threads):
        n_per_thread = n // n_threads
        thread = threading.Thread(target=insert_records, args=(n_per_thread, connections[_i][1], query, values))
        threads.append(thread)
    # Wait for all threads to complete
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    end = time.time()
    print("Total time: ", end-start, "create_records_with_threading_and_n_connections")
    while connections:
        conn, cursor = connections.pop()
        conn.commit()
        cursor.close()
        conn.close()


def max_connections():
    conn, cursor = get_connection()
    cursor.execute("SHOW max_connections")
    connection_limit = cursor.fetchone()[0]
    print("Connection limit: ", connection_limit)


def create_records_with_for_loop(n):
    conn, cursor = get_connection()

    query = "INSERT INTO customers (first_name, last_name, email, phone_number, address) VALUES (%s, %s, %s, %s, %s)"
    record = generate_record()

    start = time.time()
    for _ in range(n):
        cursor.execute(query, record)
    end = time.time()
    print("Total time: ", end - start, "create_records_with_for_loop")

    conn.commit()
    cursor.close()
    conn.close()


def get_connection():
    conn = psycopg2.connect(
        user='postgres',
        password='SIQ3PAGDL8pa',
        host='192.168.111.15',
        port='5432',
        database='forgelab'
    )
    cursor = conn.cursor()
    return conn, cursor


def generate_record():
    fake = Faker()
    first_name = fake.first_name()
    last_name = fake.last_name()
    email = fake.email()
    phone_number = fake.phone_number()[:10]
    address = fake.address()[:10]
    values = (first_name, last_name, email, phone_number, address)
    return values


if __name__ == '__main__':
    n_records = 10000
    threads_count = 10
    create_records_with_for_loop(n=n_records)
    create_records_with_threading(n=n_records, n_threads=threads_count)
    create_records_with_threading_and_n_connections(n=n_records, n_threads=threads_count)
    create_records_with_threading_get_connection_inside_the_thread(n=n_records, n_threads=threads_count)
    create_records_with_connection_pool(n=n_records, n_threads=threads_count)
    create_records_with_multiprocessing_and_connections_inside_process(n=n_records, n_processor=threads_count)
    # run_insertions_with_async(n=n_records, n_coroutines=threads_count)


"""
Total time:  47.19944095611572
"""
