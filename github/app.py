"""Point d'entrée Streamlit de WafaClub.

Lancement :
    streamlit run app.py
"""

from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="WafaClub · Fidélité & cartes cadeaux",
    page_icon="💳",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "About": "WafaClub — MVP de démonstration. Paiements simulés, aucune donnée bancaire réelle.",
    },
)

from wafaclub.config import settings  # noqa: E402
from wafaclub.db import database  # noqa: E402
from wafaclub.seed import seed_demo_data  # noqa: E402
from wafaclub.ui import components as ui  # noqa: E402
from wafaclub.ui import public, router  # noqa: E402
from wafaclub.ui.state import SS, current_lang, init_state, load_current_user  # noqa: E402
from wafaclub.ui.theme import inject_theme  # noqa: E402


@st.cache_resource(show_spinner=False)
def bootstrap() -> bool:
    """Crée les tables et le jeu de démonstration une seule fois par processus."""
    database.create_all()
    if settings.auto_seed:
        with database.session() as session:
            seed_demo_data(session)
    return True


def main() -> None:
    bootstrap()
    init_state()
    lang = current_lang()

    view = SS.get("view", "landing")
    if view == "app":
        user = load_current_user()
        if user is None:
            SS["view"] = "landing"
            st.rerun()
        inject_theme(lang, public=False)
        router.render(user)
        ui.legal_note(lang)
        return

    inject_theme(lang, public=True)
    if view == "auth":
        public.render_auth()
    else:
        public.render_landing()


if __name__ == "__main__":
    main()
