import asyncio

from db.core import init_pool, get_pool
from db.utils import normalize

BATCH = 500

async def main():
    # ✅ poolni init qilamiz (DATABASE_URL env bo‘lishi shart)
    await init_pool()

    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT channel_id, message_id, COALESCE(title_raw,title) AS t
            FROM movies
            WHERE title_norm IS NULL OR title_norm=''
        """)
        print("movies to fix:", len(rows))

        for i in range(0, len(rows), BATCH):
            batch = rows[i:i+BATCH]
            async with conn.transaction():
                for r in batch:
                    tn = normalize(r["t"])
                    await conn.execute("""
                        UPDATE movies
                        SET title_norm=$1
                        WHERE channel_id=$2 AND message_id=$3
                    """, tn, int(r["channel_id"]), int(r["message_id"]))
            print(f"movies updated: {min(i+BATCH, len(rows))}/{len(rows)}")

        arows = await conn.fetch("""
            SELECT channel_id, message_id, alias_raw AS a
            FROM movie_aliases
            WHERE alias_norm IS NULL OR alias_norm=''
        """)
        print("aliases to fix:", len(arows))

        for i in range(0, len(arows), BATCH):
            batch = arows[i:i+BATCH]
            async with conn.transaction():
                for r in batch:
                    an = normalize(r["a"])
                    await conn.execute("""
                        UPDATE movie_aliases
                        SET alias_norm=$1
                        WHERE channel_id=$2 AND message_id=$3 AND alias_raw=$4
                    """, an, int(r["channel_id"]), int(r["message_id"]), r["a"])
            print(f"aliases updated: {min(i+BATCH, len(arows))}/{len(arows)}")

    print("✅ Done.")

if __name__ == "__main__":
    asyncio.run(main())