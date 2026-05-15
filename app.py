"""
app.py
------
地籍調査日報アプリのメインファイル。
定数定義・ヘルパー関数・画面ルーティングを担当します。

起動方法:
    cd work_report_app
    streamlit run app.py
"""

import io
import json
from pathlib import Path
import streamlit as st
import database as db
from ui_pages import page_input, page_history, page_admin

# 追加作業者の保存先
_WORKERS_CONFIG = Path(__file__).parent / "data" / "workers_config.json"


def _load_extra_workers() -> list:
    """data/workers_config.json から追加作業者リストを読み込む。"""
    if _WORKERS_CONFIG.exists():
        try:
            with open(_WORKERS_CONFIG, "r", encoding="utf-8") as f:
                return json.load(f).get("extra_workers", [])
        except Exception:
            return []
    return []


def _save_extra_worker(name: str) -> str:
    """
    作業者名を workers_config.json に追記保存する。
    戻り値: "ok" / "duplicate" / "empty"
    """
    name = name.strip()
    if not name:
        return "empty"
    extras = _load_extra_workers()
    if name in WORKER_LIST or name in extras:
        return "duplicate"
    extras.append(name)
    _WORKERS_CONFIG.parent.mkdir(exist_ok=True)
    with open(_WORKERS_CONFIG, "w", encoding="utf-8") as f:
        json.dump({"extra_workers": extras}, f, ensure_ascii=False, indent=2)
    return "ok"


def _delete_extra_worker(name: str) -> bool:
    """workers_config.json から作業者を削除する。"""
    extras = _load_extra_workers()
    if name not in extras:
        return False
    extras.remove(name)
    with open(_WORKERS_CONFIG, "w", encoding="utf-8") as f:
        json.dump({"extra_workers": extras}, f, ensure_ascii=False, indent=2)
    return True


def _get_all_workers() -> list:
    """固定リスト＋追加作業者を結合して返す（重複除去）。"""
    extras = _load_extra_workers()
    combined = list(WORKER_LIST)  # コピー
    for w in extras:
        if w not in combined:
            combined.append(w)
    return combined

# ============================================================
# 定数定義（ここを変更することで選択肢を追加・変更できます）
# ============================================================

# ─────────────────────────────────────────────────────────────
# 管理者の作業者名（WORKER_LIST 内の名前と完全一致させること）
ADMIN_NAME = "石野芳治"
# ─────────────────────────────────────────────────────────────

# 作業者リスト（固定メンバー）
# ※ アプリのUI経由で追加した作業者は data/workers_config.json に保存されます
# ※ 室・西荒屋・宮坂・大根布・鶴が丘は「班名」のため、ここには含めません
WORKER_LIST = [
    "石野芳治",      # 管理者（ADMIN_NAME と一致させること）
    "古平真一",
    "森田良雄",
    "藤島信一郎",
    "寺田和彦",
    "西野勝",
    "北川巧",
    "平石ゆかり",
    "竹中蔵之助",    # ※ 蔵之介 → 蔵之助（フォームの正式表記）
    "角田之尚",
    "山村優季",
    "寺崎壱",
    "木村泰之",
    "越野真綺",
    "作業者1:深山郁",   # 旧フォームの「補助者1」
    "作業者2:角田利克", # 旧フォームの「補助者2」
]

# 班リスト
# ※ フォームの選択肢をそのまま使用
TEAM_LIST = [
    "1.室（平石）",
    "2.西荒屋（森田）",
    "3.宮坂（石野）",
    "4.大根布（藤島）",
    "5.鶴が丘ほか（角田）",
    "0総括班",
    "99作業員",
]

# 工程IDリスト: (表示ラベル, process_id, process_name)
# ※ Googleフォームの選択肢をそのまま反映（2026-05-13確認）
# ※ 工程IDと工程名はDBに分けて保存されます。
PROCESS_LIST = [
    # ─── E00〜E04 ────────────────────────────────────────────
    ("E00 打合せ",                    "E00", "打合せ"),
    ("E01 担当者募集",                "E01", "担当者募集"),
    ("E02 名簿作成",                  "E02", "名簿作成"),
    ("E03 担当者区域指定",            "E03", "担当者区域指定"),
    ("E04 工程計画作成",              "E04", "工程計画作成"),
    # ─── E11〜E16 ────────────────────────────────────────────
    ("E11 事前調査計画用データ作成",  "E11", "事前調査計画用データ作成"),
    ("E12 事前調査計画",              "E12", "事前調査計画"),
    ("E13 事前調査通知書作成",        "E13", "事前調査通知書作成"),
    ("E14 事前調査通知書確認",        "E14", "事前調査通知書確認"),
    ("E15 封詰め",                    "E15", "封詰め"),
    ("E16 発送",                      "E16", "発送"),
    # ─── E21〜E29 ────────────────────────────────────────────
    ("E21 資料調査",                  "E21", "資料調査"),
    ("E22 現地調査",                  "E22", "現地調査"),
    ("E23 測量指示図面作成",          "E23", "測量指示図面作成"),
    ("E24 仮画地作成",                "E24", "仮画地作成"),
    ("E25 比較検証",                  "E25", "比較検証"),
    ("E26 筆界案作成",                "E26", "筆界案作成"),
    ("E27 再調整",                    "E27", "再調整"),
    ("E28 筆界案再作成",              "E28", "筆界案再作成"),
    ("E29 点検・成果品作成",          "E29", "点検・成果品作成"),
    # ─── FR1〜FR6 ────────────────────────────────────────────
    ("FR1 現況測量（GNSS/RTK）",      "FR1", "現況測量（GNSS/RTK）"),
    ("FR2 現況計算（3D）",            "FR2", "現況計算（3D）"),
    ("FR3 街区・検証点観測（TS）",    "FR3", "街区・検証点観測（TS）"),
    ("FR4 現況計算（TS）",            "FR4", "現況計算（TS）"),
    ("FR5 資料とりまとめ",            "FR5", "資料とりまとめ"),
    ("FR6 点検・成果品作成",          "FR6", "点検・成果品作成"),
    # ─── E31〜E36 ────────────────────────────────────────────
    ("E31 立会計画用データ作成",      "E31", "立会計画用データ作成"),
    ("E32 立会計画",                  "E32", "立会計画"),
    ("E33 立会依頼書作成",            "E33", "立会依頼書作成"),
    ("E34 立会依頼書確認",            "E34", "立会依頼書確認"),
    ("E35 封詰め",                    "E35", "封詰め"),
    ("E36 発送",                      "E36", "発送"),
    # ─── E41〜E44 ────────────────────────────────────────────
    ("E41 筆界案同意書作成",          "E41", "筆界案同意書作成"),
    ("E42 筆界案同意書に署名",        "E42", "筆界案同意書に署名"),
    ("E43 土地調査書点検",            "E43", "土地調査書点検"),
    ("E44 点検・成果品作成",          "E44", "点検・成果品作成"),
    # ─── FR7 ─────────────────────────────────────────────────
    ("FR7 筆界案測設（TS）",          "FR7", "筆界案測設（TS）"),
    # ─── E51〜E53 ────────────────────────────────────────────
    ("E51 写真撮影",                  "E51", "写真撮影"),
    ("E52 写真点検",                  "E52", "写真点検"),
    ("E53 点検・成果品作成",          "E53", "点検・成果品作成"),
    # ─── E61〜E67 ────────────────────────────────────────────
    ("E61 土地調査書作成（元データ）","E61", "土地調査書作成（元データ）"),
    ("E62 土地調査書確認",            "E62", "土地調査書確認"),
    ("E63 説明資料作成",              "E63", "説明資料作成"),
    ("E64 現地調査・説明",            "E64", "現地調査・説明"),
    ("E65 土地調査書署名",            "E65", "土地調査書署名"),
    ("E66 土地調査書点検",            "E66", "土地調査書点検"),
    ("E67 点検・成果品作成",          "E67", "点検・成果品作成"),
    # ─── E71〜E73 ────────────────────────────────────────────
    ("E71 測量指示図面作成",          "E71", "測量指示図面作成"),
    ("E72 測量指示図面点検",          "E72", "測量指示図面点検"),
    ("E73 測量会社に送信",            "E73", "測量会社に送信"),
]

# 作業場所リスト（フォームの選択肢と同一）
WORK_PLACE_LIST = [
    "内灘",
    "自己事務所",
]

# ============================================================
# ページ設定
# ============================================================
st.set_page_config(
    page_title="地籍調査日報アプリ",
    page_icon="🗾",
    layout="wide",
)


# ============================================================
# ログイン・利用者選択画面
# ============================================================
def page_login():
    """利用者選択画面。session_stateに作業者名を保存する。"""
    st.title("🗾 地籍調査日報アプリ")
    st.markdown("### 利用者を選択してください")

    # 固定リスト＋追加作業者を結合
    all_workers = _get_all_workers()
    current = st.session_state.get("worker_name", all_workers[0])
    default_idx = all_workers.index(current) if current in all_workers else 0

    selected = st.selectbox(
        "作業者名",
        options=all_workers,
        index=default_idx,
        key="login_select",
    )

    if st.button("この名前でログイン", type="primary", use_container_width=True):
        st.session_state["worker_name"] = selected
        st.session_state["is_admin"] = (selected == ADMIN_NAME)
        st.session_state["page"] = "日報入力"
        st.rerun()

    st.markdown("---")

    # ── 作業者の追加
    with st.expander("➕ 作業者を追加する"):
        new_name = st.text_input("追加する作業者名（フルネーム）", key="new_worker_input")
        if st.button("追加する", key="btn_add_worker"):
            result = _save_extra_worker(new_name)
            if result == "ok":
                st.success(f"✅ 「{new_name.strip()}」を作業者リストに追加しました。")
                st.rerun()
            elif result == "duplicate":
                st.warning(f"⚠️ 「{new_name.strip()}」はすでにリストに存在します。")
            else:
                st.error("名前を入力してください。")

    # ── 追加作業者の削除
    extra_workers = _load_extra_workers()
    if extra_workers:
        with st.expander("🗑️ 追加した作業者を削除する"):
            del_target = st.selectbox(
                "削除する作業者名",
                options=extra_workers,
                key="del_worker_select",
            )
            if st.button("削除する", key="btn_del_worker", type="secondary"):
                if _delete_extra_worker(del_target):
                    st.success(f"✅ 「{del_target}」をリストから削除しました。")
                    st.rerun()

    st.caption("※ 同じセッション内では次回以降も自動的にこの名前が使われます。")


# ============================================================
# メイン処理（ルーティング）
# ============================================================
def main():
    """アプリのエントリーポイント。ログイン状態とサイドバーナビを管理する。"""

    # DBを初期化（テーブルがなければ作成）
    db.initialize_db()

    # ログイン前はログイン画面を表示
    if "worker_name" not in st.session_state:
        page_login()
        return

    worker_name = st.session_state["worker_name"]
    is_admin = st.session_state.get("is_admin", False)

    # ── サイドバー ──────────────────────────────
    with st.sidebar:
        st.markdown(f"### 👤 {worker_name}")
        st.markdown("---")

        # ナビゲーション項目（管理者画面は石野のみ表示）
        nav_items = ["日報入力", "自分の履歴"]
        if is_admin:
            nav_items.append("管理者画面")

        current_page = st.session_state.get("page", "日報入力")
        if current_page not in nav_items:
            current_page = "日報入力"

        for item in nav_items:
            is_current = current_page == item
            label = f"**{item}**" if is_current else item
            if st.button(label, key=f"nav_{item}", use_container_width=True):
                st.session_state["page"] = item
                st.rerun()

        st.markdown("---")
        if st.button("🔄 利用者を変更", use_container_width=True):
            del st.session_state["worker_name"]
            st.session_state.pop("is_admin", None)
            st.session_state.pop("page", None)
            st.rerun()

    # ── 画面ルーティング ──────────────────────────
    page = st.session_state.get("page", "日報入力")

    if page == "日報入力":
        page_input(
            worker_name=worker_name,
            process_list=PROCESS_LIST,
            team_list=TEAM_LIST,
            work_place_list=WORK_PLACE_LIST,
        )
    elif page == "自分の履歴":
        page_history(
            worker_name=worker_name,
            process_list=PROCESS_LIST,
            team_list=TEAM_LIST,
            work_place_list=WORK_PLACE_LIST,
        )
    elif page == "管理者画面" and is_admin:
        page_admin()
    else:
        st.error("このページは表示できません。")


if __name__ == "__main__":
    main()
else:
    main()
