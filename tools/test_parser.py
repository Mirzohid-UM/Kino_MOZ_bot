from utils.post_parser import parse_movie_post

sample = """
#Top_Film

🎬 Don 2 (2011) [HD] 720P (TV TARJIMA)
🇺🇿 O'zbek tilida (TV TARJIMA)
⚔ Janri: #Jangari #Triller #Kriminal
🎥 GOLD KINOLAR 🍿 (https://telegram.me/+xxxx)
"""

p = parse_movie_post(sample)
print("TITLE:", p.title)
print("TILI:", p.tili)
print("JANRI:", p.janri)
print("ALIASES:", p.aliases)
print("CLEAN:\\n", p.clean_text)
