import html
import sqlite3
import requests

from pathlib import Path
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)


BOT_TOKEN = Path("token.txt").read_text(encoding="utf-8").strip()
TMDB_TOKEN = Path("tmdb_token.txt").read_text(encoding="utf-8").strip()

TMDB_URL = "https://api.themoviedb.org/3"
DB_FILE = "movies.db"


def H(value):
    return html.escape(str(value or ""))


def db():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS favorites (
            user_id INTEGER,
            media_type TEXT,
            media_id INTEGER,
            title TEXT,
            PRIMARY KEY(user_id, media_type, media_id)
        )
    """)
    conn.commit()
    return conn


def tmdb(endpoint, params=None):
    response = requests.get(
        TMDB_URL + endpoint,
        headers={
            "Authorization": f"Bearer {TMDB_TOKEN}",
            "accept": "application/json",
        },
        params=params or {},
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def main_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎬 الأفلام", callback_data="browse_movie"),
            InlineKeyboardButton("📺 المسلسلات", callback_data="browse_tv"),
        ],
        [
            InlineKeyboardButton("🍥 الأنمي", callback_data="browse_anime"),
            InlineKeyboardButton("🔥 الأكثر شعبية", callback_data="browse_trending"),
        ],
        [
            InlineKeyboardButton("🆕 جديد", callback_data="browse_new"),
            InlineKeyboardButton("⭐ الأعلى تقييماً", callback_data="browse_top"),
        ],
        [
            InlineKeyboardButton("🔎 بحث", callback_data="search_help"),
            InlineKeyboardButton("❤️ قائمتي", callback_data="favorites"),
        ],
    ])


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎬 <b>مرحباً بك في بوت الأفلام</b>\n\n"
        "اختر من القائمة:",
        parse_mode="HTML",
        reply_markup=main_menu(),
    )


async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query_text = " ".join(context.args).strip()

    if not query_text:
        await update.message.reply_text(
            "🔎 اكتب اسم الفيلم بعد الأمر.\n\n"
            "مثال:\n"
            "<code>/search Spider-Man</code>",
            parse_mode="HTML",
        )
        return

    try:
        data = tmdb(
            "/search/movie",
            {
                "query": query_text,
                "language": "ar-SA",
                "include_adult": "false",
            },
        )

        results = data.get("results", [])[:10]

        if not results:
            await update.message.reply_text("❌ لم أجد الفيلم.")
            return

        buttons = []

        for movie in results:
            movie_id = movie.get("id")
            title = movie.get("title") or "بدون اسم"
            year = (movie.get("release_date") or "")[:4]

            label = f"🎬 {title}"
            if year:
                label += f" ({year})"

            buttons.append([
                InlineKeyboardButton(
                    label[:60],
                    callback_data=f"tmdb_movie_{movie_id}",
                )
            ])

        buttons.append([
            InlineKeyboardButton("🏠 الرئيسية", callback_data="home")
        ])

        await update.message.reply_text(
            "🔎 <b>نتائج البحث</b>\n\nاختر الفيلم:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(buttons),
        )

    except Exception as e:
        print("SEARCH ERROR:", e)
        await update.message.reply_text(
            "❌ حدث خطأ أثناء البحث."
        )


async def browse(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    category = query.data

    try:
        if category == "browse_movie":
            endpoint = "/movie/popular"
            title = "🎬 الأفلام"

        elif category == "browse_tv":
            endpoint = "/tv/popular"
            title = "📺 المسلسلات"

        elif category == "browse_trending":
            endpoint = "/trending/all/week"
            title = "🔥 الأكثر شعبية"

        elif category == "browse_new":
            endpoint = "/movie/now_playing"
            title = "🆕 جديد"

        elif category == "browse_top":
            endpoint = "/movie/top_rated"
            title = "⭐ الأعلى تقييماً"

        elif category == "browse_anime":
            endpoint = "/discover/tv"
            title = "🍥 الأنمي"

        else:
            return

        params = {
            "language": "ar-SA",
            "page": 1,
        }

        if category == "browse_anime":
            params.update({
                "with_genres": 16,
                "with_original_language": "ja",
                "sort_by": "popularity.desc",
            })

        data = tmdb(endpoint, params)
        results = data.get("results", [])[:10]

        if not results:
            await query.edit_message_text(
                "❌ لا توجد نتائج.",
                reply_markup=main_menu(),
            )
            return

        buttons = []

        for item in results:
            media_type = item.get("media_type")

            if not media_type:
                media_type = "tv" if item.get("name") else "movie"

            item_id = item.get("id")
            name = item.get("title") or item.get("name") or "بدون اسم"
            date = item.get("release_date") or item.get("first_air_date") or ""
            year = date[:4]

            label = f"🎬 {name}" if media_type == "movie" else f"📺 {name}"

            if year:
                label += f" ({year})"

            buttons.append([
                InlineKeyboardButton(
                    label[:60],
                    callback_data=f"tmdb_{media_type}_{item_id}",
                )
            ])

        buttons.append([
            InlineKeyboardButton("🏠 الرئيسية", callback_data="home")
        ])

        await query.edit_message_text(
            f"<b>{H(title)}</b>\n\nاختر من القائمة:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(buttons),
        )

    except Exception as e:
        print("BROWSE ERROR:", e)

        await query.edit_message_text(
            "❌ حدث خطأ أثناء جلب القائمة.",
            reply_markup=main_menu(),
        )


async def tmdb_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        _, media_type, item_id = query.data.split("_")

        response = requests.get(
            f"{TMDB_URL}/{media_type}/{item_id}",
            headers={
                "Authorization": f"Bearer {TMDB_TOKEN}",
                "accept": "application/json",
            },
            params={
                "language": "ar-SA",
            },
            timeout=20,
        )

        response.raise_for_status()
        item = response.json()

        title = item.get("title") or item.get("name") or "بدون اسم"
        overview = item.get("overview") or "لا يوجد وصف متوفر حالياً."

        date = (
            item.get("release_date")
            or item.get("first_air_date")
            or ""
        )

        year = date[:4] if date else "غير معروف"

        rating = float(item.get("vote_average") or 0)

        genres = " • ".join(
            g.get("name", "")
            for g in item.get("genres", [])
            if g.get("name")
        ) or "غير محدد"

        poster = item.get("poster_path")

        text = (
            f"🎬 <b>{H(title)}</b>\n\n"
            f"⭐ <b>التقييم:</b> {rating:.1f}/10\n"
            f"📅 <b>السنة:</b> {H(year)}\n"
            f"🎭 <b>التصنيف:</b> {H(genres)}\n"
        )

        buttons = []

        if media_type == "movie":
            runtime = item.get("runtime")

            if runtime:
                runtime_text = f"{runtime // 60}س {runtime % 60}د"
            else:
                runtime_text = "غير معروف"

            text += f"⏱️ <b>المدة:</b> {runtime_text}\n\n"

            buttons.append([
                InlineKeyboardButton(
                    "▶️ مشاهدة",
                    callback_data=f"play_movie_{item_id}",
                )
            ])

        else:
            seasons = [
                s for s in item.get("seasons", [])
                if s.get("season_number") not in (None, 0)
            ]

            text += f"📚 <b>المواسم:</b> {len(seasons)}\n\n"

        text += f"📝 <b>القصة:</b>\n{H(overview)}"

        buttons.append([
            InlineKeyboardButton(
                "❤️ إضافة للمفضلة",
                callback_data=f"fav_{media_type}_{item_id}",
            )
        ])

        buttons.append([
            InlineKeyboardButton(
                "🔙 رجوع",
                callback_data="home",
            ),
            InlineKeyboardButton(
                "🏠 الرئيسية",
                callback_data="home",
            ),
        ])

        markup = InlineKeyboardMarkup(buttons)

        if poster:
            poster_url = f"https://image.tmdb.org/t/p/w500{poster}"

            await query.message.reply_photo(
                photo=poster_url,
                caption=text[:1024],
                parse_mode="HTML",
                reply_markup=markup,
            )

            try:
                await query.message.delete()
            except Exception:
                pass

        else:
            await query.edit_message_text(
                text,
                parse_mode="HTML",
                reply_markup=markup,
            )

    except Exception as e:
        print("DETAILS ERROR:", e)

        try:
            await query.message.reply_text(
                "❌ حدث خطأ أثناء جلب تفاصيل العمل."
            )
        except Exception:
            pass


async def play_movie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        tmdb_id = int(query.data.split("_")[-1])

        text = (
            "▶️ <b>مشاهدة الفيلم</b>\n\n"
            "يمكنك فتح صفحة الفيلم الرسمية "
            "للعثور على خيارات المشاهدة المتاحة في منطقتك."
        )

        markup = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "🔗 صفحة الفيلم",
                    url=f"https://www.themoviedb.org/movie/{tmdb_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    "🔙 رجوع",
                    callback_data=f"tmdb_movie_{tmdb_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    "🏠 الرئيسية",
                    callback_data="home",
                )
            ],
        ])

        await query.message.reply_text(
            text=text,
            parse_mode="HTML",
            reply_markup=markup,
        )

    except Exception as e:
        print("PLAY ERROR:", e)
        await query.answer(
            "❌ حدث خطأ أثناء فتح المصدر.",
            show_alert=True,
        )


async def favorite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        _, media_type, item_id = query.data.split("_")
        item_id = int(item_id)

        data = tmdb(
            f"/{media_type}/{item_id}",
            {"language": "ar-SA"},
        )

        title = data.get("title") or data.get("name") or "بدون اسم"

        conn = db()

        conn.execute(
            """
            INSERT OR REPLACE INTO favorites
            (user_id, media_type, media_id, title)
            VALUES (?, ?, ?, ?)
            """,
            (
                query.from_user.id,
                media_type,
                item_id,
                title,
            ),
        )

        conn.commit()
        conn.close()

        await query.answer(
            "❤️ تمت الإضافة إلى قائمتك",
            show_alert=True,
        )

    except Exception as e:
        print("FAVORITE ERROR:", e)
        await query.answer(
            "❌ لم تتم الإضافة.",
            show_alert=True,
        )


async def favorites(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    try:
        conn = db()

        rows = conn.execute(
            """
            SELECT media_type, media_id, title
            FROM favorites
            WHERE user_id = ?
            ORDER BY rowid DESC
            """,
            (query.from_user.id,),
        ).fetchall()

        conn.close()

        if not rows:
            await query.edit_message_text(
                "❤️ <b>قائمتي</b>\n\n"
                "لا توجد أعمال محفوظة حتى الآن.",
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(
                            "🏠 الرئيسية",
                            callback_data="home",
                        )
                    ]
                ]),
            )
            return

        buttons = []

        for media_type, media_id, title in rows:
            buttons.append([
                InlineKeyboardButton(
                    f"❤️ {title}"[:60],
                    callback_data=f"tmdb_{media_type}_{media_id}",
                )
            ])

        buttons.append([
            InlineKeyboardButton(
                "🏠 الرئيسية",
                callback_data="home",
            )
        ])

        await query.edit_message_text(
            "❤️ <b>قائمتي</b>\n\nاختر عملاً:",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(buttons),
        )

    except Exception as e:
        print("FAVORITES ERROR:", e)
        await query.answer(
            "❌ حدث خطأ.",
            show_alert=True,
        )


async def search_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "🔎 <b>البحث</b>\n\n"
        "استخدم الأمر بهذا الشكل:\n\n"
        "<code>/search Spider-Man</code>\n\n"
        "ثم اختر الفيلم من النتائج.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "🏠 الرئيسية",
                    callback_data="home",
                )
            ]
        ]),
    )


async def home(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "🎬 <b>القائمة الرئيسية</b>\n\n"
        "اختر القسم الذي تريده:",
        parse_mode="HTML",
        reply_markup=main_menu(),
    )


def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT TOKEN غير موجود في token.txt")

    if not TMDB_TOKEN:
        raise RuntimeError("TMDB TOKEN غير موجود في tmdb_token.txt")

    db().close()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("search", search))

    app.add_handler(
        CallbackQueryHandler(
            browse,
            pattern=r"^browse_(movie|tv|anime|trending|new|top)$",
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            tmdb_details,
            pattern=r"^tmdb_(movie|tv)_\d+$",
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            play_movie,
            pattern=r"^play_movie_\d+$",
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            favorite,
            pattern=r"^fav_(movie|tv)_\d+$",
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            favorites,
            pattern=r"^favorites$",
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            search_help,
            pattern=r"^search_help$",
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            home,
            pattern=r"^home$",
        )
    )

    print("🎬 Movies Test Bot Started")

    app.run_polling()


if __name__ == "__main__":
    main()
