import os
from datetime import UTC, date, datetime, time
from pathlib import Path

import streamlit as st

from arducam_capture.composition import create_services
from arducam_capture.domain.errors import CameraDisconnectedError, CameraDiscoveryError
from arducam_capture.domain.models.capture import CaptureFilters, CaptureStatus
from arducam_capture.platform.config import AppSettings

st.set_page_config(page_title="Arducam Capture", page_icon="📷", layout="wide")
st.title("Arducam Capture")
with st.sidebar:
    if st.button("Quitter", help="Ferme l'application et libère la caméra"):
        st.success("Arducam Capture est fermée. Vous pouvez fermer cet onglet.")
        os._exit(0)
st.warning(
    "Le pilotage réel de la B0494C (Windows/DirectShow) n'est pas encore validé sur matériel. "
    "Les captures sont simulées si le backend « fake » est actif."
)


@st.cache_resource
def services_for_data_dir(data_dir: str):
    return create_services(Path(data_dir))


services = services_for_data_dir(str(AppSettings().resolved_data_dir()))
try:
    cameras = services.discovery.list_available_cameras()
except CameraDiscoveryError as error:
    st.error(f"Erreur de détection des caméras (différente d'une caméra absente) : {error}")
    st.stop()
if not cameras:
    st.error("Aucune caméra Arducam détectée. Vérifiez la connexion USB 3.0 puis rechargez.")
    st.stop()
camera = cameras[0]
capabilities = services.control.get_capabilities(camera.camera_id)

capture_tab, history_tab, export_tab, diagnostic_tab = st.tabs(
    ["Caméra / Capture", "Historique", "Exporter", "Diagnostic"]
)

with capture_tab:
    st.subheader(camera.name)
    st.caption("Aucune capacité n'est présentée comme disponible sauf si l'adaptateur la déclare.")
    if st.button("Actualiser l'aperçu"):
        st.image(services.preview.get_frame(camera.camera_id), caption="Aperçu (basse résolution)")
    resolution = st.selectbox(
        "Résolution de capture",
        capabilities.supported_resolutions,
        format_func=lambda value: f"{value[0]} × {value[1]}",
    )
    for control, control_range in capabilities.supported_controls.items():
        current = services.control.get_control(camera.camera_id, control) or control_range.minimum
        value = st.slider(
            control.value.replace("_", " ").title(),
            control_range.minimum,
            control_range.maximum,
            current,
            step=control_range.step,
            key=f"control-{control.value}",
        )
        if value != current:
            services.control.set_control(camera.camera_id, control, value)
    if st.button("Capturer", type="primary"):
        with st.spinner("Capture en cours (plusieurs secondes en 108 MP)…"):
            try:
                result = services.capture.capture(camera.camera_id, *resolution)
            except CameraDisconnectedError:
                st.error("Caméra déconnectée. Rebranchez-la puis rechargez la page.")
                st.stop()
        st.success(f"Capture enregistrée : {result.file_name}")
        st.image(services.history.read_image(result.capture_id))

with history_tab:
    st.subheader("Historique des captures")
    filters_enabled = st.checkbox("Filtrer par période")
    start_day = st.date_input("Du", value=date.today(), disabled=not filters_enabled)
    end_day = st.date_input("Au", value=date.today(), disabled=not filters_enabled)
    selected_status = st.selectbox("Statut", ["Tous", *[item.value for item in CaptureStatus]])
    start_utc = datetime.combine(start_day, time.min, tzinfo=UTC) if filters_enabled else None
    end_utc = datetime.combine(end_day, time.max, tzinfo=UTC) if filters_enabled else None
    filters = CaptureFilters(
        camera_id=camera.camera_id,
        status=None if selected_status == "Tous" else CaptureStatus(selected_status),
        start_utc=start_utc,
        end_utc=end_utc,
    )
    records = services.history.list_captures(filters)
    for record in records:
        with st.container(border=True):
            st.write(
                f"**{record.file_name}** — {record.width} × {record.height} — "
                f"{record.created_at_utc} — {record.status}"
            )
            if record.status == CaptureStatus.CAPTURED.value:
                st.image(services.history.read_image(record.id), width=320)
            confirmation_key = f"confirm-{record.id}"
            if st.button("Supprimer", key=f"delete-{record.id}"):
                st.session_state[confirmation_key] = True
            if st.session_state.get(confirmation_key):
                if st.button("Confirmer la suppression", key=confirmation_key):
                    services.history.delete_capture(record.id, confirmed=True)
                    st.session_state.pop(confirmation_key, None)
                    st.rerun()

with export_tab:
    st.subheader("Exporter l'historique")
    export_filters = CaptureFilters(camera_id=camera.camera_id)
    st.download_button(
        "Télécharger le CSV",
        services.export.export_csv(export_filters),
        file_name="captures.csv",
        mime="text/csv",
    )
    st.download_button(
        "Télécharger le fichier Excel",
        services.export.export_excel(export_filters),
        file_name="captures.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

with diagnostic_tab:
    st.subheader("Diagnostic")
    report = services.diagnostic.build_report()
    st.json(
        {
            "Python": report.python_version,
            "Système": report.os_name,
            "Caméras": list(report.camera_names),
            "Répertoire de données": report.data_dir,
            "Base de données": report.database_path,
            "Base présente": report.database_exists,
            "Espace disque libre (Mo)": report.free_disk_bytes // (1024 * 1024),
            "Journaux": list(report.log_files),
        }
    )
