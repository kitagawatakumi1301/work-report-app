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
import extra_streamlit_components as stx
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
# カスタムCSS（モバイルレスポンシブ対応）
# ============================================================
st.markdown("""
<style>
/* ────────────────────────────────────────────────────────────
   Google Fonts 読み込み
   ──────────────────────────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700&display=swap');

/* ────────────────────────────────────────────────────────────
   全体のベーススタイル
   ──────────────────────────────────────────────────────────── */
html, body, [class*="css"] {
    font-family: 'Noto Sans JP', sans-serif !important;
}

/* メインコンテナの余白調整（モバイル時） */
.main .block-container {
    padding-top: 1.5rem;
    padding-bottom: 2rem;
}

/* ────────────────────────────────────────────────────────────
   ボタンのタッチフレンドリー化
   ──────────────────────────────────────────────────────────── */
.stButton > button {
    min-height: 48px;
    font-size: 1rem;
    font-weight: 500;
    border-radius: 10px;
    transition: all 0.2s ease;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}
.stButton > button:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(37, 99, 235, 0.25);
}
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #2563EB, #1D4ED8);
    border: none;
    color: white;
}
.stButton > button[kind="primary"]:hover {
    background: linear-gradient(135deg, #1D4ED8, #1E40AF);
}

/* ────────────────────────────────────────────────────────────
   入力フィールドのタッチ最適化
   ──────────────────────────────────────────────────────────── */
.stSelectbox > div > div,
.stDateInput > div > div > input,
.stTimeInput > div > div > input,
.stTextInput > div > div > input,
.stTextArea > div > div > textarea {
    min-height: 44px;
    font-size: 1rem !important;
    border-radius: 8px;
}

/* セレクトボックスのドロップダウン項目 */
[data-baseweb="select"] [role="option"] {
    min-height: 44px;
    padding: 10px 12px;
    font-size: 0.95rem;
}

/* ラベルの視認性向上 */
.stSelectbox label,
.stDateInput label,
.stTimeInput label,
.stTextInput label,
.stTextArea label {
    font-weight: 500;
    font-size: 0.9rem;
    color: #374151;
    margin-bottom: 4px;
}

/* ────────────────────────────────────────────────────────────
   情報カード・アラートのスタイル改善
   ──────────────────────────────────────────────────────────── */
.stAlert {
    border-radius: 10px;
    border-left-width: 4px;
}
div[data-testid="stInfo"] {
    background-color: #EFF6FF;
    border-left-color: #2563EB;
}
div[data-testid="stSuccess"] {
    background-color: #F0FDF4;
    border-left-color: #16A34A;
}
div[data-testid="stWarning"] {
    background-color: #FFFBEB;
    border-left-color: #D97706;
}
div[data-testid="stError"] {
    background-color: #FEF2F2;
    border-left-color: #DC2626;
}

/* ────────────────────────────────────────────────────────────
   タイトル・ヘッダーの改善
   ──────────────────────────────────────────────────────────── */
h1 {
    font-weight: 700 !important;
    color: #1E293B !important;
    letter-spacing: -0.02em;
}
h2, h3, h4 {
    font-weight: 600 !important;
    color: #334155 !important;
}

/* ────────────────────────────────────────────────────────────
   サイドバーの改善
   ──────────────────────────────────────────────────────────── */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #F8FAFC, #EFF6FF);
    border-right: 1px solid #E2E8F0;
}
section[data-testid="stSidebar"] .stButton > button {
    min-height: 48px;
    font-size: 0.95rem;
    border-radius: 8px;
    margin-bottom: 4px;
}

/* ────────────────────────────────────────────────────────────
   データテーブルの改善
   ──────────────────────────────────────────────────────────── */
.stDataFrame {
    border-radius: 10px;
    overflow: hidden;
    box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}

/* ────────────────────────────────────────────────────────────
   タブの改善
   ──────────────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
    gap: 2px;
}
.stTabs [data-baseweb="tab"] {
    min-height: 44px;
    padding: 8px 16px;
    font-weight: 500;
    border-radius: 8px 8px 0 0;
}

/* ────────────────────────────────────────────────────────────
   エクスパンダーの改善
   ──────────────────────────────────────────────────────────── */
.streamlit-expanderHeader {
    min-height: 48px;
    font-size: 1rem;
    font-weight: 500;
}

/* ────────────────────────────────────────────────────────────
   区切り線
   ──────────────────────────────────────────────────────────── */
hr {
    border-color: #E2E8F0 !important;
    margin: 1.5rem 0 !important;
}

/* ────────────────────────────────────────────────────────────
   ダウンロードボタン
   ──────────────────────────────────────────────────────────── */
.stDownloadButton > button {
    min-height: 48px;
    font-size: 1rem;
    border-radius: 10px;
    border: 2px solid #2563EB;
    color: #2563EB;
    font-weight: 500;
    transition: all 0.2s ease;
}
.stDownloadButton > button:hover {
    background-color: #2563EB;
    color: white;
}

/* ════════════════════════════════════════════════════════════
   モバイルレスポンシブ（768px以下）
   ════════════════════════════════════════════════════════════ */
@media (max-width: 768px) {
    /* メインコンテナの余白を縮小 */
    .main .block-container {
        padding-left: 1rem;
        padding-right: 1rem;
        padding-top: 1rem;
        max-width: 100%;
    }

    /* 2列レイアウトを1列に */
    div[data-testid="column"] {
        width: 100% !important;
        flex: 1 1 100% !important;
        min-width: 100% !important;
    }

    /* タイトルのフォントサイズ縮小 */
    h1 {
        font-size: 1.5rem !important;
    }
    h2, h3 {
        font-size: 1.15rem !important;
    }
    h4 {
        font-size: 1rem !important;
    }

    /* ボタンをさらに大きく */
    .stButton > button {
        min-height: 52px;
        font-size: 1.05rem;
    }

    /* 入力フィールドの拡大 */
    .stSelectbox > div > div,
    .stDateInput > div > div > input,
    .stTimeInput > div > div > input,
    .stTextInput > div > div > input {
        min-height: 48px;
        font-size: 1.05rem !important;
    }

    /* ドロップダウンの選択肢を大きく */
    [data-baseweb="select"] [role="option"] {
        min-height: 48px;
        padding: 12px 14px;
        font-size: 1rem;
    }

    /* テーブルフォントサイズ */
    .stDataFrame table {
        font-size: 0.8rem;
    }

    /* タブを横スクロール可能に */
    .stTabs [data-baseweb="tab-list"] {
        overflow-x: auto;
        -webkit-overflow-scrolling: touch;
        flex-wrap: nowrap;
    }
    .stTabs [data-baseweb="tab"] {
        min-height: 40px;
        padding: 6px 12px;
        font-size: 0.85rem;
        white-space: nowrap;
    }

    /* サイドバーボタン */
    section[data-testid="stSidebar"] .stButton > button {
        min-height: 52px;
        font-size: 1rem;
    }

    /* ラジオボタンを大きく */
    .stRadio > div {
        gap: 8px;
    }
    .stRadio label {
        min-height: 44px;
        display: flex;
        align-items: center;
        font-size: 1rem;
    }
}

/* ════════════════════════════════════════════════════════════
   さらに小さい画面（480px以下）
   ════════════════════════════════════════════════════════════ */
@media (max-width: 480px) {
    .main .block-container {
        padding-left: 0.5rem;
        padding-right: 0.5rem;
    }

    h1 {
        font-size: 1.3rem !important;
    }

    /* テーブルはさらに小さく */
    .stDataFrame table {
        font-size: 0.75rem;
    }
}
</style>
""", unsafe_allow_html=True)




# ============================================================
# ログイン・利用者選択画面
# ============================================================
def page_login(cookie_manager):
    """利用者選択画面。session_stateに作業者名を保存する。"""

    # ── アプリヘッダー（カード風デザイン）
    st.markdown("""
    <div style="text-align:center;padding:2rem 1rem 1rem;">
        <div style="font-size:3rem;margin-bottom:0.5rem;">🗾</div>
        <h1 style="font-size:1.8rem;margin:0;color:#1E293B;">地籍調査日報アプリ</h1>
        <p style="color:#6B7280;font-size:0.9rem;margin-top:0.3rem;">作業日報の入力・管理</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div style="background:white;border-radius:12px;padding:4px;
                box-shadow:0 2px 8px rgba(0,0,0,0.08);margin-bottom:1rem;">
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### 👤 利用者を選択してください")

    # 固定リスト＋追加作業者を結合
    all_workers = _get_all_workers()
    
    # Cookieから前回ログインしたユーザーを取得
    saved_worker = cookie_manager.get(cookie="saved_worker_name")
    
    current = st.session_state.get("worker_name", saved_worker if saved_worker in all_workers else all_workers[0])
    default_idx = all_workers.index(current) if current in all_workers else 0

    selected = st.selectbox(
        "作業者名",
        options=all_workers,
        index=default_idx,
        key="login_select",
    )

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    if st.button("✅ この名前でログイン", type="primary", use_container_width=True):
        st.session_state["worker_name"] = selected
        st.session_state["is_admin"] = (selected == ADMIN_NAME)
        st.session_state["page"] = "日報入力"
        # ログアウトフラグを解除
        st.session_state.pop("logged_out", None)
        # Cookieに保存 (有効期限を約1年に設定)
        cookie_manager.set("saved_worker_name", selected, key="set_worker_cookie", max_age=31536000)
        st.rerun()

    st.markdown("---")

    # ── 作業者の追加
    with st.expander("➕ 作業者を追加する"):
        new_name = st.text_input("追加する作業者名（フルネーム）", key="new_worker_input")
        if st.button("追加する", key="btn_add_worker", use_container_width=True):
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
            if st.button("削除する", key="btn_del_worker", type="secondary", use_container_width=True):
                if _delete_extra_worker(del_target):
                    st.success(f"✅ 「{del_target}」をリストから削除しました。")
                    st.rerun()

    st.caption("※ 次回以降は自動的に前回の名前でログインされます。")


# ============================================================
# メイン処理（ルーティング）
# ============================================================
def main():
    """アプリのエントリーポイント。ログイン状態とサイドバーナビを管理する。"""

    # モバイルでの自動キーボード起動を抑制するJavaScript
    st.components.v1.html(
        """
        <script>
        const doc = window.parent.document;
        
        function applyMobileFriendly() {
            // 1. セレクトボックス内の検索入力欄を readonly にする（キーボードを抑制）
            const selectInputs = doc.querySelectorAll('div[data-baseweb="select"] input');
            selectInputs.forEach(input => {
                if (!input.hasAttribute('readonly')) {
                    input.setAttribute('readonly', 'true');
                    input.setAttribute('inputmode', 'none');
                    input.style.caretColor = 'transparent';
                }
            });
        
            // 2. 日付入力欄を readonly にする
            const dateInputs = doc.querySelectorAll('div.stDateInput input');
            dateInputs.forEach(input => {
                if (!input.hasAttribute('readonly')) {
                    input.setAttribute('readonly', 'true');
                    input.setAttribute('inputmode', 'none');
                    input.style.caretColor = 'transparent';
                }
            });
        }
        
        // 画面切り替え等によるDOMの再レンダリングを動的に監視して適用
        const observer = new MutationObserver((mutations) => {
            applyMobileFriendly();
        });
        
        observer.observe(doc.body, {
            childList: true,
            subtree: true
        });
        
        // 初回呼び出し
        applyMobileFriendly();
        </script>
        """,
        height=0,
        width=0,
    )

    # DBを初期化（テーブルがなければ作成）
    db.initialize_db()

    # Cookieマネージャーの初期化（※ stx.CookieManagerは1回の描画で1つだけインスタンス化する）
    cookie_manager = stx.CookieManager()

    # ログイン前はログイン画面を表示
    if "worker_name" not in st.session_state:
        saved_worker = cookie_manager.get(cookie="saved_worker_name")
        # Cookieに値があり、かつ「明示的にログアウトした直後」でない場合は自動ログイン
        if saved_worker and saved_worker in _get_all_workers() and not st.session_state.get("logged_out"):
            st.session_state["worker_name"] = saved_worker
            st.session_state["is_admin"] = (saved_worker == ADMIN_NAME)
            st.session_state["page"] = "日報入力"
            st.rerun()
        else:
            page_login(cookie_manager)
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
                st.session_state["should_close_sidebar"] = True
                st.rerun()

        st.markdown("---")
        if st.button("🔄 利用者を変更", use_container_width=True):
            del st.session_state["worker_name"]
            st.session_state.pop("is_admin", None)
            st.session_state.pop("page", None)
            st.session_state["should_close_sidebar"] = True
            # Cookieを削除し、自動ログインを防ぐフラグを立てる
            cookie_manager.delete("saved_worker_name", key="del_worker_cookie")
            st.session_state["logged_out"] = True
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

    # ── モバイル環境で画面遷移後にサイドバーを自動的に閉じる ─────────────────
    if st.session_state.get("should_close_sidebar", False):
        st.session_state["should_close_sidebar"] = False  # フラグをリセット
        js_code = """
<img src="x" style="display:none;" onerror="
    (function() {
        var sidebar = document.querySelector('section[data-testid=\\'stSidebar\\']');
        if (sidebar) {
            var rect = sidebar.getBoundingClientRect();
            var isMobile = (window.innerWidth <= 768 || document.documentElement.clientWidth <= 768);
            if (isMobile && rect.left >= 0 && rect.width > 0) {
                var closeBtn = sidebar.querySelector('[data-testid=\\'stSidebarCollapseButton\\']');
                if (closeBtn) {
                    closeBtn.click();
                }
            }
        }
    })();
">
"""
        st.markdown(js_code, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
else:
    main()
