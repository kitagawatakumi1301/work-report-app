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
    st.info(f"作業者：**{worker_name}**　（変更はサイドバーの「利用者を変更」から）")

    process_labels = [p[0] for p in process_list]

    col1, col2 = st.columns(2)
    with col1:
        work_date = st.date_input("作業日 *", value=date.today())
        team = st.selectbox("班 *", options=team_list)
        work_place = st.selectbox("作業場所 *", options=work_place_list)
    with col2:
        process_label = st.selectbox("工程ID *", options=process_labels)
        start_time_val = st.time_input("作業開始時刻 *", value=time(9, 0), step=1800)
        end_time_val = st.time_input("作業終了時刻 *", value=time(17, 0), step=1800)

    # 作業時間プレビュー
    if end_time_val != start_time_val:
        hours = calc_hours(start_time_val, end_time_val)
        st.success(f"⏱ 作業時間：{format_duration(hours)}　（{format_time_span(start_time_val, end_time_val)}）")
    elif end_time_val == start_time_val:
        hours = 0.0
        st.warning("開始時刻と終了時刻が同じです。")

    note = st.text_area("備考", placeholder="特記事項があれば入力してください")
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
            msgs = [f"・{o['work_date']} {o['start_time']}〜{o['end_time']} ({o['process_id']} {o['process_name']})" for o in overlaps]
            st.warning(
                f"⚠️ **時間帯が重複しています**\n\n"
                f"{work_date.strftime('%m月%d日')} {format_time_span(start_time_val, end_time_val)} と重複している登録：\n\n"
                + "\n".join(msgs)
                + "\n\n重複登録すると時給・交通費の二重計上が発生する可能性があります。"
            )
            st.session_state["pending_save"] = dict(
                worker_name=worker_name, work_date=work_date_str, team=team,
                process_id=process_id, process_name=process_name, process_type=process_type,
                start_time=start_str, end_time=end_str, hours=hours,
                work_place=work_place, note=note,
            )
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("❌ 保存しない", use_container_width=True):
                    st.session_state.pop("pending_save", None)
                    st.info("保存をキャンセルしました。")
            with col_b:
                if st.button("⚠️ それでも保存する", use_container_width=True):
                    _execute_save(st.session_state.pop("pending_save"))
            return

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
    """    履歴一覧 + インライン編集・削除を統合した画面。
    一覧から日報を選ぶと「編集する」「削除する」の選択肢が出る。
    """
    # 60秒ごとに自動更新（最新データを反映）
    st_autorefresh(interval=60_000, limit=None, key="history_autorefresh")

    st.title("📋 自分の入力履歴")
    st.info(f"作業者：**{worker_name}**")

    if "save_success_msg" in st.session_state:
        st.success(st.session_state.pop("save_success_msg"))
        st.balloons()

    rows = _cached_get_reports_by_worker(worker_name)
    if not rows:
        st.info("まだ日報が登録されていません。")
        return

    df = pd.DataFrame(rows)

    # ── フィルター
    st.markdown("#### フィルター")
    fc1, fc2, fc3, fc4 = st.columns(4)
    with fc1:
        months = sorted(df["work_date"].str[:7].unique(), reverse=True)
        sel_month = st.selectbox("月", ["すべて"] + list(months), key="h_month")
    with fc2:
        sel_team = st.selectbox("班", ["すべて"] + sorted(df["team"].unique()), key="h_team")
    with fc3:
        sel_proc = st.selectbox("工程ID", ["すべて"] + sorted(df["process_id"].unique()), key="h_proc")
    with fc4:
        sel_place = st.selectbox("作業場所", ["すべて"] + sorted(df["work_place"].unique()), key="h_place")

    fdf = df.copy()
    if sel_month != "すべて":
        fdf = fdf[fdf["work_date"].str[:7] == sel_month]
    if sel_team != "すべて":
        fdf = fdf[fdf["team"] == sel_team]
    if sel_proc != "すべて":
        fdf = fdf[fdf["process_id"] == sel_proc]
    if sel_place != "すべて":
        fdf = fdf[fdf["work_place"] == sel_place]

    if fdf.empty:
        st.info("フィルター条件に一致するデータがありません。")
        return

    disp = fdf[["id", "work_date", "team", "process_id", "process_name",
                "start_time", "end_time", "hours", "work_place", "note"]].copy()
    disp["hours"] = disp["hours"].apply(format_duration)
    disp.columns = ["ID", "作業日", "班", "工程ID", "工程名",
                    "開始", "終了", "作業時間", "場所", "備考"]
    st.markdown(f"**{len(disp)} 件**")
    st.dataframe(disp, use_container_width=True, hide_index=True)

    # ── 編集・削除するレコードを選択
    st.markdown("---")
    st.markdown("#### 編集・削除")

    # 削除確認フェーズの管理（セレクトボックスとは完全に独立）
    if "h_del_target_id" not in st.session_state:
        st.session_state["h_del_target_id"] = None

    if "h_edit_key" not in st.session_state:
        st.session_state["h_edit_key"] = 0

    fdf = fdf.copy()
    fdf["label"] = (
        fdf["work_date"] + "  " +
        fdf["process_id"] + " " + fdf["process_name"] + "  " +
        fdf["start_time"] + "〜" + fdf["end_time"] +
        "  [ID:" + fdf["id"].astype(str) + "]"
    )
    opts = ["（選択してください）"] + fdf["label"].tolist()

    # ── フェーズ1: 削除確認画面中の場合、セレクトボックスを表示しない
    if st.session_state["h_del_target_id"] is not None:
        target_id = st.session_state["h_del_target_id"]
        rec = _cached_get_report_by_id(target_id)
        if rec is None:
            st.session_state["h_del_target_id"] = None
            st.rerun()
            return

        st.error(
            f"「{rec['work_date']}　{rec['process_id']} {rec['process_name']}　"
            f"{rec['start_time']}〜{rec['end_time']}」\n\n"
            "この日報を削除しますか？削除すると元に戻せません。"
        )
        cy, cn = st.columns(2)
        with cy:
            if st.button("🗑️ はい、削除します", type="primary", use_container_width=True, key="h_del_yes"):
                if db.delete_report(target_id):
                    st.session_state["save_success_msg"] = "🗑️ 日報を削除しました。"
                _clear_cache()
                st.session_state["h_del_target_id"] = None
                st.session_state["h_edit_key"] += 1
                st.rerun()
        with cn:
            if st.button("キャンセル", use_container_width=True, key="h_del_no"):
                st.session_state["h_del_target_id"] = None
                st.rerun()
        return

    # ── フェーズ2: 通常の編集・削除選択画面
    sel_label = st.selectbox("操作する日報を選択", opts, key=f"h_edit_{st.session_state['h_edit_key']}")
    if sel_label == "（選択してください）":
        return

    rec = _cached_get_report_by_id(int(fdf[fdf["label"] == sel_label].iloc[0]["id"]))
    if rec is None:
        st.error("レコードが見つかりません。")
        return

    action = st.radio("操作を選択してください",
                      ["✏️ 編集する", "🗑️ 削除する"],
                      horizontal=True, key="h_action")
    st.markdown("---")

    # ═ 編集フォーム
    if action == "✏️ 編集する":
        st.markdown("##### 編集フォーム")
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
            new_start = st.time_input("開始時刻", value=time(h_s, m_s), step=1800)
            new_end   = st.time_input("終了時刻", value=time(h_e, m_e), step=1800)
        if new_end != new_start:
            new_hours = calc_hours(new_start, new_end)
            st.success(f"⏱ 作業時間：{format_duration(new_hours)}　（{format_time_span(new_start, new_end)}）")
        else:
            new_hours = 0.0
            st.error("開始時刻と終了時刻が同じです。")
        new_note = st.text_area("備考", value=rec.get("note", "") or "")

        c_save, c_cancel = st.columns(2)
        with c_save:
            btn_save = st.button("💾 保存する", type="primary", use_container_width=True)
        with c_cancel:
            btn_cancel = st.button("キャンセル", key="h_edit_cancel", use_container_width=True)

        if btn_cancel:
            st.session_state["h_edit_key"] += 1
            st.rerun()

        if btn_save:
            if new_end == new_start:
                st.error("開始時刻と終了時刻は別の時刻にしてください。")
                return
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
                st.session_state["h_edit_key"] += 1
                st.session_state["page"] = "自分の履歴"
                st.rerun()
            else:
                st.error("更新に失敗しました。")

    # ═ 削除: ボタンを押したら確認フェーズに移行（履歴画面に一度戻ってから表示）
    else:
        if st.button("🗑️ 削除を確認する", type="secondary", use_container_width=True, key="h_del_confirm"):
            st.session_state["h_del_target_id"] = int(rec["id"])
            st.rerun()



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
    st.markdown("### フィルター")
    fc1, fc2, fc3, fc4, fc5 = st.columns(5)
    with fc1:
        months = sorted(df["month"].unique(), reverse=True)
        sel_month = st.selectbox("月", ["すべて"] + list(months), key="a_month")
    with fc2:
        sel_worker = st.selectbox("作業者", ["すべて"] + sorted(df["worker_name"].unique()), key="a_worker")
    with fc3:
        sel_team = st.selectbox("班", ["すべて"] + sorted(df["team"].unique()), key="a_team")
    with fc4:
        sel_proc = st.selectbox("工程ID", ["すべて"] + sorted(df["process_id"].unique()), key="a_proc")
    with fc5:
        sel_place = st.selectbox("作業場所", ["すべて"] + sorted(df["work_place"].unique()), key="a_place")

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
