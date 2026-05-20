"""
ui_pages.py
-----------
各画面のUIコンポーネント。
- page_input   : 日報入力
- page_history : 自分の履歴
- page_edit    : 編集・削除
- page_admin   : 管理者専用画面
"""

import io
from datetime import date, time, datetime

import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh

import database as db


# ============================================================
# キャッシュ付きDBアクセス関数（60秒間キャッシュ）
# ============================================================

@st.cache_data(ttl=60)
def _cached_get_reports_by_worker(worker_name: str) -> list:
    return db.get_reports_by_worker(worker_name)

@st.cache_data(ttl=60)
def _cached_get_all_reports() -> list:
    return db.get_all_reports()

@st.cache_data(ttl=60)
def _cached_get_report_by_id(report_id: int):
    return db.get_report_by_id(report_id)

@st.cache_data(ttl=60)
def _cached_summary_monthly_user_hours() -> list:
    return db.get_summary_monthly_user_hours()

@st.cache_data(ttl=60)
def _cached_summary_monthly_user_process_hours() -> list:
    return db.get_summary_monthly_user_process_hours()

@st.cache_data(ttl=60)
def _cached_summary_e_attendance_days() -> list:
    return db.get_summary_e_attendance_days()

@st.cache_data(ttl=60)
def _cached_summary_e_attendance_dates() -> list:
    return db.get_summary_e_attendance_dates()

@st.cache_data(ttl=60)
def _cached_summary_fr_hours() -> list:
    return db.get_summary_fr_hours()

@st.cache_data(ttl=60)
def _cached_summary_process_hours() -> list:
    return db.get_summary_process_hours()

def _clear_cache():
    """書き込み後にキャッシュを全クリアして最新データを取得できるようにする"""
    st.cache_data.clear()


# ============================================================
# ヘルパー関数
# ============================================================

def get_process_type(process_id: str) -> str:
    if process_id.startswith("E"):
        return "E"
    elif process_id.startswith("FR"):
        return "FR"
    return "OTHER"


def calc_hours(start: time, end: time) -> float:
    start_minutes = start.hour * 60 + start.minute
    end_minutes = end.hour * 60 + end.minute
    if end_minutes < start_minutes:
        end_minutes += 24 * 60
    return (end_minutes - start_minutes) / 60.0


def format_duration(hours) -> str:
    try:
        total_minutes = int(round(float(hours) * 60))
    except (TypeError, ValueError):
        return ""

    sign = "-" if total_minutes < 0 else ""
    total_minutes = abs(total_minutes)
    hour_part, minute_part = divmod(total_minutes, 60)

    if hour_part and minute_part:
        return f"{sign}{hour_part}時間{minute_part}分"
    if hour_part:
        return f"{sign}{hour_part}時間"
    return f"{sign}{minute_part}分"


def format_time_span(start: time, end: time) -> str:
    if end < start:
        return f"{start.strftime('%H:%M')} 〜 翌日{end.strftime('%H:%M')}"
    return f"{start.strftime('%H:%M')} 〜 {end.strftime('%H:%M')}"


def get_process_info_by_label(label: str, process_list: list) -> tuple:
    for lbl, pid, pname in process_list:
        if lbl == label:
            return pid, pname
    return "OTHER", "その他"


def get_process_label_by_id(process_id: str, process_list: list) -> str:
    for lbl, pid, _ in process_list:
        if pid == process_id:
            return lbl
    return process_id


def to_excel_bytes(dfs: dict) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        for sheet_name, df in dfs.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)
    return buf.getvalue()


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")


# ============================================================
# 2. 日報入力画面
# ============================================================

def page_input(worker_name: str, process_list: list, team_list: list, work_place_list: list):
    """日報を新規入力してDBに保存する。重複チェック・バリデーション付き。"""
    st.title("📝 日報入力")
    st.markdown(
        f'<div style="background:linear-gradient(135deg,#EFF6FF,#DBEAFE);'
        f'padding:12px 16px;border-radius:10px;margin-bottom:1rem;">'
        f'<span style="font-size:1.05rem;">👤 <strong>{worker_name}</strong></span>'
        f'<span style="color:#6B7280;font-size:0.85rem;margin-left:8px;">'
        f'（変更はサイドバーから）</span></div>',
        unsafe_allow_html=True,
    )

    # ── 重複確認ダイアログの表示モード
    if st.session_state.get("show_overlap_warning"):
        pending = st.session_state.get("pending_save")
        if pending:
            overlaps = db.check_overlap(
                pending["worker_name"], pending["work_date"],
                pending["start_time"], pending["end_time"]
            )
            msgs = [f"・{o['work_date']} {o['start_time']}〜{o['end_time']} ({o['process_id']} {o['process_name']})" for o in overlaps]
            st.warning(
                f"⚠️ **時間帯が重複しています**\n\n"
                f"{pending['work_date']} {pending['start_time']}〜{pending['end_time']} と重複している登録：\n\n"
                + "\n".join(msgs)
                + "\n\n重複登録すると時給・交通費の二重計上が発生する可能性があります。"
            )
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("❌ 保存しない", use_container_width=True, key="btn_overlap_cancel"):
                    st.session_state.pop("pending_save", None)
                    st.session_state["show_overlap_warning"] = False
                    st.info("保存をキャンセルしました。")
                    st.rerun()
            with col_b:
                if st.button("⚠️ それでも保存する", use_container_width=True, type="primary", key="btn_overlap_confirm"):
                    data = st.session_state.pop("pending_save", None)
                    st.session_state["show_overlap_warning"] = False
                    if data:
                        _execute_save(data)
            return

    process_labels = [p[0] for p in process_list]

    # ── 行1: 作業日・工程
    col1, col2 = st.columns(2)
    with col1:
        work_date = st.date_input("📅 作業日 *", value=date.today())
    with col2:
        process_label = st.selectbox("🔧 工程ID *", options=process_labels)

    # ── 行2: 開始・終了時刻
    time_options = [f"{h:02d}:{m:02d}" for h in range(24) for m in (0, 30)]
    default_start_idx = time_options.index("09:00") if "09:00" in time_options else 18
    default_end_idx = time_options.index("17:00") if "17:00" in time_options else 34

    col3, col4 = st.columns(2)
    with col3:
        start_time_str = st.selectbox("⏰ 開始時刻 *", options=time_options, index=default_start_idx)
        start_time_val = time(*map(int, start_time_str.split(":")))
    with col4:
        end_time_str = st.selectbox("⏰ 終了時刻 *", options=time_options, index=default_end_idx)
        end_time_val = time(*map(int, end_time_str.split(":")))

    # 作業時間プレビュー
    if end_time_val != start_time_val:
        hours = calc_hours(start_time_val, end_time_val)
        st.markdown(
            f'<div style="background:linear-gradient(135deg,#F0FDF4,#DCFCE7);'
            f'padding:12px 16px;border-radius:10px;border-left:4px solid #16A34A;">'
            f'⏱ <strong>作業時間：{format_duration(hours)}</strong>'
            f'<span style="color:#6B7280;margin-left:8px;">'
            f'（{format_time_span(start_time_val, end_time_val)}）</span></div>',
            unsafe_allow_html=True,
        )
    elif end_time_val == start_time_val:
        hours = 0.0
        st.warning("開始時刻と終了時刻が同じです。")

    # ── 作業者名に応じたデフォルト班の決定（部分一致で柔軟に判定）
    default_team = None
    if "石野" in worker_name:
        default_team = "0総括班"
    elif "平石" in worker_name:
        default_team = "1.室（平石）"
    elif any(name in worker_name for name in ["森田", "北川", "竹中"]):
        default_team = "2.西荒屋（森田）"
    elif any(name in worker_name for name in ["寺田", "西野"]):
        default_team = "3.宮坂（石野）"
    elif "藤島" in worker_name:
        default_team = "4.大根布（藤島）"
    elif any(name in worker_name for name in ["角田", "山村", "寺崎", "越野", "深山"]):
        default_team = "5.鶴が丘ほか（角田）"
    elif "今村" in worker_name:
        default_team = "99作業員"

    default_team_idx = 0
    if default_team and default_team in team_list:
        default_team_idx = team_list.index(default_team)

    # ── 行3: 班・場所
    col5, col6 = st.columns(2)
    with col5:
        team = st.selectbox("👥 班 *", options=team_list, index=default_team_idx)
    with col6:
        work_place = st.selectbox("📍 作業場所 *", options=work_place_list)

    note = st.text_area("📝 備考", placeholder="特記事項があれば入力してください")
    st.markdown("---")

    if st.button("📥 日報を保存する", type="primary", use_container_width=True):
        # ── バリデーション
        errors = []
        if not work_date:
            errors.append("作業日を入力してください。")
        if end_time_val == start_time_val:
            errors.append("開始時刻と終了時刻は別の時刻にしてください。")
        if hours <= 0:
            errors.append("作業時間が0以下です。時刻を確認してください。")
        if errors:
            for e in errors:
                st.error(e)
            return

        process_id, process_name = get_process_info_by_label(process_label, process_list)
        process_type = get_process_type(process_id)
        work_date_str = work_date.strftime("%Y-%m-%d")
        start_str = start_time_val.strftime("%H:%M")
        end_str = end_time_val.strftime("%H:%M")

        # ── 重複チェック（時間帯の重なりも検出）
        overlaps = db.check_overlap(worker_name, work_date_str, start_str, end_str)
        if overlaps:
            st.session_state["pending_save"] = dict(
                worker_name=worker_name, work_date=work_date_str, team=team,
                process_id=process_id, process_name=process_name, process_type=process_type,
                start_time=start_str, end_time=end_str, hours=hours,
                work_place=work_place, note=note,
            )
            st.session_state["show_overlap_warning"] = True
            st.rerun()

        # 重複なし → そのまま保存
        _execute_save(dict(
            worker_name=worker_name, work_date=work_date_str, team=team,
            process_id=process_id, process_name=process_name, process_type=process_type,
            start_time=start_str, end_time=end_str, hours=hours,
            work_place=work_place, note=note,
        ))


def _execute_save(data: dict):
    """
    日報データをDBに保存する。
    保存後は「自分の履歴」画面へ自動遷移する。
    """
    new_id = db.insert_report(data)
    _clear_cache()  # 保存後にキャッシュをクリア
    # 遷移後の画面で成功メッセージを表示するため session_state に保存
    st.session_state["save_success_msg"] = f"✅ 日報を保存しました（ID: {new_id}）"
    # 「自分の履歴」画面へ遷移
    st.session_state["page"] = "自分の履歴"
    st.rerun()



# ============================================================
# 3. 自分の履歴（編集・削除を統合）
# ============================================================

def page_history(worker_name: str, process_list: list, team_list: list, work_place_list: list):
    """履歴一覧 + ワンタップ直接編集・削除画面。"""
    # 60秒ごとに自動更新（最新データを反映）
    st_autorefresh(interval=60_000, limit=None, key="history_autorefresh")

    st.title("📋 自分の入力履歴")
    st.markdown(
        f'<div style="background:linear-gradient(135deg,#EFF6FF,#DBEAFE);'
        f'padding:12px 16px;border-radius:10px;margin-bottom:1rem;">'
        f'<span style="font-size:1.05rem;">👤 <strong>{worker_name}</strong></span></div>',
        unsafe_allow_html=True,
    )

    if "save_success_msg" in st.session_state:
        st.success(st.session_state.pop("save_success_msg"))
        st.balloons()

    # セッションステート初期化
    if "h_selected_id" not in st.session_state:
        st.session_state["h_selected_id"] = None
    if "h_del_target_id" not in st.session_state:
        st.session_state["h_del_target_id"] = None

    # ── フェーズ1: 削除確認画面（最優先）
    if st.session_state["h_del_target_id"] is not None:
        target_id = st.session_state["h_del_target_id"]
        rec = _cached_get_report_by_id(target_id)
        if rec is None:
            st.error("対象の日報が見つかりません。")
            st.session_state["h_del_target_id"] = None
            st.rerun()
            return

        st.markdown("### ⚠️ 日報の削除確認")
        st.markdown("---")
        st.error(
            f"**以下の日報を完全に削除しますか？この操作は元に戻せません。**\n\n"
            f"・**作業日**: {rec['work_date']}\n"
            f"・**班**: {rec['team']}\n"
            f"・**工程**: {rec['process_id']} {rec['process_name']}\n"
            f"・**時間**: {rec['start_time']} 〜 {rec['end_time']} ({format_duration(rec['hours'])})\n"
            f"・**場所**: {rec['work_place']}\n"
            f"・**備考**: {rec.get('note') or ''}"
        )

        c_del_yes, c_del_no = st.columns(2)
        with c_del_yes:
            if st.button("🗑️ はい、完全に削除します", type="primary", use_container_width=True, key="h_del_confirm_yes"):
                if db.delete_report(target_id):
                    st.session_state["save_success_msg"] = "🗑️ 日報を削除しました。"
                    _clear_cache()
                else:
                    st.error("削除に失敗しました。")
                st.session_state["h_del_target_id"] = None
                st.session_state["h_selected_id"] = None
                st.rerun()
        with c_del_no:
            if st.button("キャンセル", use_container_width=True, key="h_del_confirm_no"):
                st.session_state["h_del_target_id"] = None
                st.rerun()
        return

    # ── フェーズ2: 直接編集フォーム（編集ボタンが押された場合）
    if st.session_state["h_selected_id"] is not None:
        target_id = st.session_state["h_selected_id"]
        rec = _cached_get_report_by_id(target_id)
        if rec is None:
            st.error("レコードが見つかりません。")
            st.session_state["h_selected_id"] = None
            st.rerun()
            return

        # 画面を最上部にスクロールさせるCORS対応・安全なリトライ型JavaScriptインジェクション
        # ※Markdownのインデントによる意図せぬコードブロック化を防ぐため、文字列の左端のインデントを完全に排除しています。
        st.markdown(
            """<img src="x" style="display:none;" onerror='
(function() {
    function resetScroll() {
        var selectors = [".main", "div[data-testid=\\"stAppViewContainer\\"]", "div.block-container"];
        try { window.scrollTo(0, 0); } catch(e) {}
        try {
            document.documentElement.scrollTop = 0;
            document.body.scrollTop = 0;
        } catch(e) {}
        selectors.forEach(function(sel) {
            try {
                var el = document.querySelector(sel);
                if (el) {
                    el.scrollTop = 0;
                    if (typeof el.scrollTo === "function") {
                        el.scrollTo(0, 0);
                    }
                }
            } catch(e) {}
        });
    }
    resetScroll();
    setTimeout(resetScroll, 10);
    setTimeout(resetScroll, 50);
    setTimeout(resetScroll, 100);
    setTimeout(resetScroll, 300);
    setTimeout(resetScroll, 600);
    setTimeout(resetScroll, 1000);
})();
'>""",
            unsafe_allow_html=True
        )

        st.markdown("### ✏️ 日報の編集")
        st.markdown("---")

        process_labels = [p[0] for p in process_list]
        current_label = get_process_label_by_id(rec["process_id"], process_list)
        col1, col2 = st.columns(2)
        with col1:
            new_date  = st.date_input("作業日", value=date.fromisoformat(rec["work_date"]))
            new_team  = st.selectbox("班", team_list,
                                     index=team_list.index(rec["team"]) if rec["team"] in team_list else 0)
            new_place = st.selectbox("作業場所", work_place_list,
                                     index=work_place_list.index(rec["work_place"]) if rec["work_place"] in work_place_list else 0)
        with col2:
            new_proc_label = st.selectbox("工程ID", process_labels,
                                          index=process_labels.index(current_label) if current_label in process_labels else 0)
            h_s, m_s = map(int, rec["start_time"].split(":"))
            h_e, m_e = map(int, rec["end_time"].split(":"))
            
            time_options_edit = [f"{h:02d}:{m:02d}" for h in range(24) for m in (0, 30)]
            start_str_init = f"{h_s:02d}:{m_s:02d}"
            end_str_init = f"{h_e:02d}:{m_e:02d}"
            
            if start_str_init not in time_options_edit:
                time_options_edit.append(start_str_init)
                time_options_edit.sort()
            if end_str_init not in time_options_edit:
                time_options_edit.append(end_str_init)
                time_options_edit.sort()
                
            idx_start = time_options_edit.index(start_str_init)
            idx_end = time_options_edit.index(end_str_init)
            
            new_start_str = st.selectbox("開始時刻", options=time_options_edit, index=idx_start)
            new_end_str   = st.selectbox("終了時刻", options=time_options_edit, index=idx_end)
            
            new_start = time(*map(int, new_start_str.split(":")))
            new_end   = time(*map(int, new_end_str.split(":")))
        if new_end != new_start:
            new_hours = calc_hours(new_start, new_end)
            st.success(f"⏱ 作業時間：{format_duration(new_hours)}　（{format_time_span(new_start, new_end)}）")
        else:
            new_hours = 0.0
            st.error("開始時刻と終了時刻が同じです。")
        new_note = st.text_area("備考", value=rec.get("note", "") or "")

        c_save, c_cancel = st.columns(2)
        with c_save:
            btn_save = st.button("💾 保存する", type="primary", use_container_width=True, key="h_edit_save_btn")
        with c_cancel:
            btn_cancel = st.button("キャンセル", key="h_edit_cancel", use_container_width=True)

        if btn_cancel:
            st.session_state["h_selected_id"] = None
            st.rerun()

        if btn_save:
            if new_end == new_start:
                st.error("開始時刻と終了時刻は別の時刻にしてください。")
            elif new_hours <= 0:
                st.error("作業時間が0以下です。時刻を確認してください。")
            else:
                new_proc_id, new_proc_name = get_process_info_by_label(new_proc_label, process_list)
                new_proc_type = get_process_type(new_proc_id)
                update_data = dict(
                    work_date=new_date.strftime("%Y-%m-%d"), team=new_team,
                    process_id=new_proc_id, process_name=new_proc_name, process_type=new_proc_type,
                    start_time=new_start.strftime("%H:%M"), end_time=new_end.strftime("%H:%M"),
                    hours=new_hours, work_place=new_place, note=new_note,
                )
                overlaps = db.check_overlap(worker_name, update_data["work_date"],
                                            update_data["start_time"], update_data["end_time"],
                                            exclude_id=rec["id"])
                if overlaps:
                    msgs = [f"・{o['work_date']} {o['start_time']}〜{o['end_time']} ({o['process_id']})" for o in overlaps]
                    st.warning("⚠️ 時間帯が他の日報と重複しています：\n\n" + "\n".join(msgs))
                
                if db.update_report(rec["id"], update_data):
                    st.session_state["save_success_msg"] = "✅ 日報を更新しました。"
                    _clear_cache()
                    st.session_state["h_selected_id"] = None
                    st.rerun()
                else:
                    st.error("更新に失敗しました。")

        # ── 赤背景の「削除する」エリア ─────────────────
        st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)
        st.markdown("---")
        st.markdown(
            """
            <div style="background-color:#FEF2F2; padding:12px 16px; border-radius:10px; border:1px solid #FCA5A5; margin-bottom:12px;">
                <span style="color:#991B1B; font-weight:bold; font-size:0.95rem;">⚠️ この日報の削除</span>
                <p style="color:#7F1D1D; font-size:0.85rem; margin:4px 0 0 0;">
                    この日報を完全に削除します。削除したデータは元に戻せません。
                </p>
            </div>
            <style>
            .delete-btn-box div.stButton > button {
                background: linear-gradient(135deg, #EF4444, #DC2626) !important;
                color: white !important;
                border: none !important;
            }
            .delete-btn-box div.stButton > button:hover {
                background: linear-gradient(135deg, #DC2626, #B91C1C) !important;
                box-shadow: 0 4px 12px rgba(220, 38, 38, 0.35) !important;
            }
            </style>
            """,
            unsafe_allow_html=True
        )
        
        st.markdown('<div class="delete-btn-box">', unsafe_allow_html=True)
        if st.button("🗑️ この日報を削除する", use_container_width=True, key="h_edit_delete_btn"):
            st.session_state["h_del_target_id"] = int(rec["id"])
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
        return

    # ── 通常の履歴表示画面（一覧のみ、フィルターなし）
    rows = _cached_get_reports_by_worker(worker_name)
    if not rows:
        st.info("まだ日報が登録されていません。")
        return

    fdf = pd.DataFrame(rows)

    st.markdown(f"**{len(fdf)} 件**")

    # ── 履歴のカスタムテーブル表示（ボタン付き）
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    
    # レスポンシブ＆コンパクト化のためのカスタムCSSを注入
    st.markdown("""
<style>
/* PC表示（画面幅 >= 1025px）の時の制御 */
@media (min-width: 1025px) {
    /* PC表示用のグリッドヘッダー */
    .history-header-grid {
        display: grid;
        grid-template-columns: 0.8fr 1.2fr 1.2fr 2.0fr 2.2fr 0.9fr 2.5fr;
        gap: 1rem;
        width: 100%;
        align-items: center;
        padding-bottom: 4px;
    }
    .history-header-grid > div {
        font-size: 0.85rem;
        font-weight: bold;
        color: #1E293B;
    }

    /* 7カラムある履歴行のテキストとボタンをコンパクト化 */
    div[data-testid="stHorizontalBlock"]:has(> div[data-testid="column"]:nth-child(7)) p,
    div[data-testid="stHorizontalBlock"]:has(> div[data-testid="column"]:nth-child(7)) span,
    div[data-testid="stHorizontalBlock"]:has(> div[data-testid="column"]:nth-child(7)) strong {
        font-size: 0.85rem !important;
        margin: 0 !important;
        line-height: 1.3 !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
    }

    /* 7列目の備考欄だけは長文が想定されるので、適宜折り返しを可能にする */
    div[data-testid="stHorizontalBlock"]:has(> div[data-testid="column"]:nth-child(7)) > div[data-testid="column"]:nth-child(7) p {
        white-space: normal !important;
        word-break: break-all !important;
        text-overflow: clip !important;
    }

    /* 7列の中のボタンの高さと文字サイズを制限してコンパクトに */
    div[data-testid="stHorizontalBlock"]:has(> div[data-testid="column"]:nth-child(7)) button {
        font-size: 0.8rem !important;
        min-height: 28px !important;
        height: 28px !important;
        padding: 0px 4px !important;
        line-height: 1 !important;
    }

    /* スマホ用の要素をPCでは完全に隠す */
    .mobile-history-card,
    .mobile-edit-btn-wrapper,
    .mobile-history-hr {
        display: none !important;
    }

    /* マーカー隣接セレクタによる、スマホ用編集ボタンの完全非表示化 */
    .mobile-btn-marker {
        display: none !important;
    }
    div:has(> .mobile-btn-marker) {
        display: none !important;
    }
    div:has(> .mobile-btn-marker) + div {
        display: none !important;
    }
}

/* スマホ表示（画面幅 <= 1024px）の時の制御 */
@media (max-width: 1024px) {
    /* マーカー要素自体を隠す（ボタンは隠さない） */
    .mobile-btn-marker {
        display: none !important;
    }
    div:has(> .mobile-btn-marker) {
        display: none !important;
    }

    /* PC用の7カラム履歴テーブルおよびマーカー要素を確実に隠す */
    .pc-row-marker {
        display: none !important;
    }
    div:has(> .pc-row-marker) {
        display: none !important;
    }
    div:has(> .pc-row-marker) + div {
        display: none !important;
    }
    div[data-testid="stHorizontalBlock"] {
        display: none !important;
    }
    .pc-history-hr {
        display: none !important;
    }
    .history-header-grid, .history-header-hr {
        display: none !important;
    }
    
    /* スマホ用カードの美しいデザイン */
    .mobile-history-card {
        background: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 16px;
        margin-top: 8px;
        margin-bottom: 8px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
    }
    
    /* 日付を1.5倍にする */
    .mobile-card-date {
        font-size: 1.25rem !important; /* 標準(0.85rem)の約1.5倍 */
        font-weight: bold !important;
        color: #1E293B !important;
        margin-bottom: 12px !important;
        border-bottom: 2px solid #3B82F6;
        padding-bottom: 6px;
    }
    
    .mobile-card-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 8px;
        margin-bottom: 8px;
    }
    
    .mobile-card-row {
        margin-bottom: 6px;
        font-size: 0.9rem !important;
        color: #334155;
        line-height: 1.4 !important;
    }
    
    .mobile-card-label {
        font-weight: bold;
        color: #64748B;
        margin-right: 6px;
    }
    
    .mobile-card-note {
        word-break: break-all;
        white-space: pre-wrap;
        background: #F1F5F9;
        padding: 6px 10px;
        border-radius: 6px;
        display: block;
        margin-top: 4px;
        border: 1px solid #E2E8F0;
    }
    
    /* スマホ用の「上記の日報を編集する」ボタンのスタイル調整 */
    .mobile-edit-btn-wrapper {
        margin-top: 4px;
        margin-bottom: 16px;
        padding: 0 4px;
    }
    .mobile-edit-btn-wrapper div.stButton > button {
        background: linear-gradient(135deg, #2563EB, #1D4ED8) !important;
        color: white !important;
        border: none !important;
        font-size: 0.95rem !important;
        font-weight: bold !important;
        height: 42px !important;
        border-radius: 8px !important;
        box-shadow: 0 4px 6px rgba(37, 99, 235, 0.2) !important;
        transition: all 0.2s ease !important;
    }
    .mobile-edit-btn-wrapper div.stButton > button:hover {
        background: linear-gradient(135deg, #1D4ED8, #1E40AF) !important;
        box-shadow: 0 6px 12px rgba(37, 99, 235, 0.3) !important;
        transform: translateY(-1px) !important;
    }
}
</style>
""", unsafe_allow_html=True)

    # PC表示時は st.columns と同じ比率で並び、スマホ表示時は非表示になるレスポンシブなヘッダー
    st.markdown(
        """
        <div class="history-header-grid">
            <div>操作</div>
            <div>作業日</div>
            <div>班</div>
            <div>工程</div>
            <div>時間</div>
            <div>場所</div>
            <div>備考</div>
        </div>
        <hr class="history-header-hr" style='margin: 0.2rem 0; border-color: #CBD5E1;' />
        """,
        unsafe_allow_html=True
    )

    for idx, row in fdf.iterrows():
        # --- 1. PC用の行（7カラム） ---
        with st.container():
            st.markdown('<div class="pc-row-marker"></div>', unsafe_allow_html=True)
            r_cols = st.columns([0.8, 1.2, 1.2, 2.0, 2.2, 0.9, 2.5])
            with r_cols[0]:
                if st.button("編集", key=f"btn_edit_row_{row['id']}", use_container_width=True):
                    st.session_state["h_selected_id"] = int(row["id"])
                    st.session_state["h_action"] = "編集する"
                    st.rerun()
            with r_cols[1]:
                st.markdown(row['work_date'])
            with r_cols[2]:
                st.markdown(row['team'])
            with r_cols[3]:
                st.markdown(f"{row['process_id']} {row['process_name']}")
            with r_cols[4]:
                duration_str = format_duration(row['hours'])
                st.markdown(f"{row['start_time']}〜{row['end_time']} ({duration_str})")
            with r_cols[5]:
                st.markdown(row['work_place'])
            with r_cols[6]:
                st.markdown(row.get('note') or "")
            
            # PC用の区切り線（スマホでは非表示にするため pc-row-marker を付与）
            st.markdown("<hr class='pc-row-marker pc-history-hr' style='margin: 0.2rem 0; border-color: #E2E8F0;' />", unsafe_allow_html=True)

        # --- 2. スマホ用のカード型行 ---
        with st.container():
            duration_str = format_duration(row['hours'])
            note_val = row.get('note') or "（なし）"
            
            card_html = f"""
            <div class="mobile-history-card">
                <div class="mobile-card-date">📅 {row['work_date']}</div>
                <div class="mobile-card-grid">
                    <div><span class="mobile-card-label">班:</span> {row['team']}</div>
                    <div><span class="mobile-card-label">場所:</span> {row['work_place']}</div>
                </div>
                <div class="mobile-card-row"><span class="mobile-card-label">工程:</span> {row['process_id']} {row['process_name']}</div>
                <div class="mobile-card-row"><span class="mobile-card-label">時間:</span> {row['start_time']}〜{row['end_time']} ({duration_str})</div>
                <div class="mobile-card-row">
                    <span class="mobile-card-label">備考:</span>
                    <span class="mobile-card-note">{note_val}</span>
                </div>
            </div>
            """
            st.markdown(card_html, unsafe_allow_html=True)
            
            # 「上記の日報を編集する」ボタン
            st.markdown('<div class="mobile-edit-btn-wrapper">', unsafe_allow_html=True)
            # PC表示のときにボタンを隠すためのマーカーを直前に配置
            st.markdown('<div class="mobile-btn-marker"></div>', unsafe_allow_html=True)
            if st.button("📝 上記の日報を編集する", key=f"btn_edit_row_mobile_{row['id']}", use_container_width=True):
                st.session_state["h_selected_id"] = int(row["id"])
                st.session_state["h_action"] = "編集する"
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
            
            # スマホ用の区切り線
            st.markdown("<hr class='mobile-history-hr' style='margin: 0.8rem 0; border-color: #E2E8F0;' />", unsafe_allow_html=True)




# ============================================================
# 4. 管理者専用画面
# ============================================================

def page_admin():
    """管理者（石野）専用。全員の日報確認・集計・CSV/Excel出力。"""
    # 60秒ごとに自動更新（全員の入力をリアルタイムで反映）
    st_autorefresh(interval=60_000, limit=None, key="admin_autorefresh")

    st.title("🔐 管理者専用画面")

    if "admin_success_msg" in st.session_state:
        st.success(st.session_state.pop("admin_success_msg"))

    rows = _cached_get_all_reports()
    if not rows:
        st.info("日報データがありません。")
        return

    df = pd.DataFrame(rows)
    df["month"] = df["work_date"].str[:7]

    # ── フィルター
    st.markdown("### 🔍 フィルター")
    # モバイル対応: 2行に分割（2+3 → 2+2+1）
    fc1, fc2 = st.columns(2)
    with fc1:
        months = sorted(df["month"].unique(), reverse=True)
        sel_month = st.selectbox("月", ["すべて"] + list(months), key="a_month")
    with fc2:
        sel_worker = st.selectbox("作業者", ["すべて"] + sorted(df["worker_name"].unique()), key="a_worker")
    fc3, fc4, fc5 = st.columns(3)
    with fc3:
        sel_team = st.selectbox("班", ["すべて"] + sorted(df["team"].unique()), key="a_team")
    with fc4:
        sel_proc = st.selectbox("工程ID", ["すべて"] + sorted(df["process_id"].unique()), key="a_proc")
    with fc5:
        sel_place = st.selectbox("場所", ["すべて"] + sorted(df["work_place"].unique()), key="a_place")

    fdf = df.copy()
    if sel_month != "すべて":
        fdf = fdf[fdf["month"] == sel_month]
    if sel_worker != "すべて":
        fdf = fdf[fdf["worker_name"] == sel_worker]
    if sel_team != "すべて":
        fdf = fdf[fdf["team"] == sel_team]
    if sel_proc != "すべて":
        fdf = fdf[fdf["process_id"] == sel_proc]
    if sel_place != "すべて":
        fdf = fdf[fdf["work_place"] == sel_place]

    # ── 並び替え設定
    st.markdown("##### 並び替え")
    sort_opts = {
        "作業日（新しい順）":  ("work_date",   False),
        "作業日（古い順）":    ("work_date",   True),
        "作業者名（昇順）":  ("worker_name", True),
        "作業者名（降順）":  ("worker_name", False),
        "工程ID（昇順）":   ("process_id",  True),
    }
    sel_sort = st.selectbox("並び替え順序", list(sort_opts.keys()), key="a_sort_sel")
    sort_col_key, sort_asc = sort_opts[sel_sort]

    # ── 全日報一覧
    disp_cols = ["id", "work_date", "worker_name", "team", "process_id", "process_name",
                 "start_time", "end_time", "hours", "work_place", "note", "created_at", "updated_at"]
    fdf_disp = fdf[disp_cols].sort_values(sort_col_key, ascending=sort_asc).copy()
    fdf_disp["hours"] = fdf_disp["hours"].apply(format_duration)
    st.markdown(f"### 全作業日報一覧　({len(fdf_disp)} 件)")
    st.dataframe(fdf_disp.rename(columns={
        "id": "ID", "work_date": "作業日", "worker_name": "作業者", "team": "班",
        "process_id": "工程ID", "process_name": "工程名",
        "start_time": "開始", "end_time": "終了", "hours": "作業時間",
        "work_place": "場所", "note": "備考",
        "created_at": "登録日時", "updated_at": "更新日時",
    }), use_container_width=True, hide_index=True)

    # ── 管理者向け 削除機能
    st.markdown("---")
    st.markdown("### 🗑️ 日報の削除")

    # 削除確認フェーズの管理（セレクトボックスとは独立したステートで制御）
    if "admin_del_target_id" not in st.session_state:
        st.session_state["admin_del_target_id"] = None

    # ── フェーズ1: 削除対象を選択中（確認画面ではない）
    if st.session_state["admin_del_target_id"] is None:
        fdf_admin = fdf.copy()
        fdf_admin["label"] = (
            fdf_admin["work_date"] + "  " +
            fdf_admin["worker_name"] + "  " +
            fdf_admin["process_id"] + " " + fdf_admin["process_name"] + "  " +
            fdf_admin["start_time"] + "〜" + fdf_admin["end_time"] +
            "  [ID:" + fdf_admin["id"].astype(str) + "]"
        )
        opts_admin = ["（選択してください）"] + fdf_admin["label"].tolist()
        sel_admin_label = st.selectbox("削除する日報を選択", opts_admin, key="admin_del_selectbox")

        if sel_admin_label != "（選択してください）":
            selected_id = int(fdf_admin[fdf_admin["label"] == sel_admin_label].iloc[0]["id"])
            if st.button("🗑️ この日報を削除する", type="secondary", use_container_width=True, key="admin_del_step1"):
                st.session_state["admin_del_target_id"] = selected_id
                st.rerun()

    # ── フェーズ2: 削除確認画面（セレクトボックスは表示しない）
    else:
        target_id = st.session_state["admin_del_target_id"]
        rec_admin = db.get_report_by_id(target_id)
        if rec_admin:
            st.error(
                f"【作業者】 {rec_admin['worker_name']}\n\n"
                f"【日時】 {rec_admin['work_date']} {rec_admin['start_time']}〜{rec_admin['end_time']}\n\n"
                f"【工程】 {rec_admin['process_id']} {rec_admin['process_name']}\n\n"
                "この日報を削除しますか？削除すると元に戻せません。"
            )
            c1, c2 = st.columns(2)
            with c1:
                if st.button("🗑️ はい、削除します", type="primary", key="admin_del_yes", use_container_width=True):
                    if db.delete_report(target_id):
                        st.session_state["admin_success_msg"] = "🗑️ 日報を削除しました。"
                    st.session_state["admin_del_target_id"] = None
                    st.rerun()
            with c2:
                if st.button("キャンセル", key="admin_del_no", use_container_width=True):
                    st.session_state["admin_del_target_id"] = None
                    st.rerun()
        else:
            st.session_state["admin_del_target_id"] = None
            st.rerun()

    st.markdown("---")

    # ── 集計タブ（上部フィルターが連動する）
    st.info(
        "💡 上部の「フィルター」で月・作業者・工程IDを選ぶと、"
        "集計タブA〜Eの内容もその条件で絞り込まれます。"
    )
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "A. 月別・作業者別",
        "B. 月別・作業者別・工程別",
        "C. E工程 出勤日数",
        "D. FR工程 作業時間",
        "E. 工程ID別",
    ])

    with tab1:
        st.markdown("#### A. 月別・作業者別 合計作業時間")
        data_a = _cached_summary_monthly_user_hours()
        if data_a:
            dfa = pd.DataFrame(data_a)
            dfa.columns = ["月", "作業者", "合計時間"]
            dfa["合計時間"] = dfa["合計時間"].apply(format_duration)
            # 上部フィルターを適用
            if sel_month != "すべて":
                dfa = dfa[dfa["月"] == sel_month]
            if sel_worker != "すべて":
                dfa = dfa[dfa["作業者"] == sel_worker]
            st.caption(f"表示件数：{len(dfa)} 件")
            st.dataframe(dfa, use_container_width=True, hide_index=True)
        else:
            st.info("データがありません。")

    with tab2:
        st.markdown("#### B. 月別・作業者別・工程ID別 合計作業時間")
        data_b = _cached_summary_monthly_user_process_hours()
        if data_b:
            dfb = pd.DataFrame(data_b)
            dfb.columns = ["月", "作業者", "工程ID", "工程名", "合計時間"]
            dfb["合計時間"] = dfb["合計時間"].apply(format_duration)
            if sel_month != "すべて":
                dfb = dfb[dfb["月"] == sel_month]
            if sel_worker != "すべて":
                dfb = dfb[dfb["作業者"] == sel_worker]
            if sel_proc != "すべて":
                dfb = dfb[dfb["工程ID"] == sel_proc]
            st.caption(f"表示件数：{len(dfb)} 件")
            st.dataframe(dfb, use_container_width=True, hide_index=True)
        else:
            st.info("データがありません。")

    with tab3:
        st.markdown("#### C. E工程 出勤日数集計")
        st.caption("※ 同じ作業者が同じ日に複数のE工程を入力しても、出勤日数は1日としてカウントします。")
        data_c = _cached_summary_e_attendance_days()
        if data_c:
            dfc = pd.DataFrame(data_c)
            dfc.columns = ["月", "作業者", "E工程出勤日数"]
            if sel_month != "すべて":
                dfc = dfc[dfc["月"] == sel_month]
            if sel_worker != "すべて":
                dfc = dfc[dfc["作業者"] == sel_worker]
            st.caption(f"表示件数：{len(dfc)} 件")
            st.dataframe(dfc, use_container_width=True, hide_index=True)
        else:
            st.info("E工程のデータがありません。")

        with st.expander("E工程 出勤日一覧を確認"):
            data_c2 = _cached_summary_e_attendance_dates()
            if data_c2:
                dfc2 = pd.DataFrame(data_c2)
                dfc2.columns = ["月", "作業者", "出勤日"]
                if sel_month != "すべて":
                    dfc2 = dfc2[dfc2["月"] == sel_month]
                if sel_worker != "すべて":
                    dfc2 = dfc2[dfc2["作業者"] == sel_worker]
                st.dataframe(dfc2, use_container_width=True, hide_index=True)

    with tab4:
        st.markdown("#### D. FR工程 作業時間集計")
        data_d = _cached_summary_fr_hours()
        if data_d:
            dfd = pd.DataFrame(data_d)
            dfd.columns = ["月", "作業者", "工程ID", "工程名", "FR合計時間"]
            dfd["FR合計時間"] = dfd["FR合計時間"].apply(format_duration)
            if sel_month != "すべて":
                dfd = dfd[dfd["月"] == sel_month]
            if sel_worker != "すべて":
                dfd = dfd[dfd["作業者"] == sel_worker]
            if sel_proc != "すべて":
                dfd = dfd[dfd["工程ID"] == sel_proc]
            st.caption(f"表示件数：{len(dfd)} 件")
            st.dataframe(dfd, use_container_width=True, hide_index=True)
        else:
            st.info("FR工程のデータがありません。")

    with tab5:
        st.markdown("#### E. 工程ID別 合計時間")
        data_e = _cached_summary_process_hours()
        if data_e:
            dfe = pd.DataFrame(data_e)
            dfe.columns = ["月", "工程ID", "工程名", "合計時間"]
            dfe["合計時間"] = dfe["合計時間"].apply(format_duration)
            if sel_month != "すべて":
                dfe = dfe[dfe["月"] == sel_month]
            if sel_proc != "すべて":
                dfe = dfe[dfe["工程ID"] == sel_proc]
            st.caption(f"表示件数：{len(dfe)} 件")
            st.dataframe(dfe, use_container_width=True, hide_index=True)
        else:
            st.info("データがありません。")

    st.markdown("---")

    # ── CSV / Excel 出力
    st.markdown("### 📤 データ出力")

    # CSV（全日報）
    export_reports = fdf[disp_cols].copy()
    export_reports["hours"] = export_reports["hours"].apply(format_duration)
    csv_bytes = to_csv_bytes(export_reports)
    st.download_button(
        label="📄 全日報データをCSVでダウンロード",
        data=csv_bytes,
        file_name=f"work_reports_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
        mime="text/csv",
        use_container_width=True,
    )

    # Excel（複数シート）
    # ※ pd.DataFrame(list_of_dicts, columns=[...])はキー名で列を選択するため、
    #   日本語列名を指定するとNaNになる。renameで列名を変換する。
    def build_excel() -> bytes:
        sheets = {}

        # シート名はExcelのシートタブに表示される名前（31文字以内）
        sheets["全日報データ"] = export_reports.rename(columns={
            "id": "ID", "work_date": "作業日", "worker_name": "作業者",
            "team": "班", "process_id": "工程ID", "process_name": "工程名",
            "start_time": "開始時刻", "end_time": "終了時刻", "hours": "作業時間",
            "work_place": "作業場所", "note": "備考",
            "created_at": "登録日時", "updated_at": "更新日時",
        })

        if data_a:
            tmp = pd.DataFrame(data_a)
            tmp.columns = ["月", "作業者", "合計時間"]
            tmp["合計時間"] = tmp["合計時間"].apply(format_duration)
            sheets["A_月別作業者別"] = tmp

        if data_b:
            tmp = pd.DataFrame(data_b)
            tmp.columns = ["月", "作業者", "工程ID", "工程名", "合計時間"]
            tmp["合計時間"] = tmp["合計時間"].apply(format_duration)
            sheets["B_月別作業者工程別"] = tmp

        if data_c:
            tmp = pd.DataFrame(data_c)
            tmp.columns = ["月", "作業者", "E工程出勤日数"]
            sheets["C_E工程出勤日数"] = tmp

        if data_d:
            tmp = pd.DataFrame(data_d)
            tmp.columns = ["月", "作業者", "工程ID", "工程名", "FR合計時間"]
            tmp["FR合計時間"] = tmp["FR合計時間"].apply(format_duration)
            sheets["D_FR工程時間"] = tmp

        if data_e:
            tmp = pd.DataFrame(data_e)
            tmp.columns = ["月", "工程ID", "工程名", "合計時間"]
            tmp["合計時間"] = tmp["合計時間"].apply(format_duration)
            sheets["E_工程ID別時間"] = tmp

        return to_excel_bytes(sheets)

    st.download_button(
        label="📊 全集計データをExcel（複数シート）でダウンロード",
        data=build_excel(),
        file_name=f"work_reports_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )
