"""
Campi AML (antiriciclaggio) e helper per filtrare output e template.
"""

from typing import Dict, List


def build_aml_template_columns(max_people: int = 5) -> List[str]:
    """Ritorna l'elenco colonne AML per output template (nomi compatti e chiari)."""
    columns = [
        "AZ_TipoSoggetto",
        "AZ_RagioneSociale",
        "AZ_FormaGiuridica",
        "AZ_CF",
        "AZ_PIVA",
        "AZ_REA",
        "AZ_ATECO",
        "AZ_Attivita",
        "AZ_Sede_Indirizzo",
        "AZ_Sede_Comune",
        "AZ_Sede_CAP",
        "AZ_Sede_Provincia",
        "AZ_Sede_Stato",
        "AZ_DataCostituzione",
        "ID_Tipo",
        "ID_Data",
        "PEP",
        "DOC_Tipo",
        "DOC_Numero",
        "DOC_Autorita",
        "DOC_DataRilascio",
        "DOC_DataScadenza",
    ]

    for i in range(1, max_people + 1):
        columns.extend(
            [
                f"P{i}_Ruolo",
                f"P{i}_Nome",
                f"P{i}_Cognome",
                f"P{i}_AmbiguitaNome",
                f"P{i}_CF",
                f"P{i}_Quota",
                f"P{i}_Sesso",
                f"P{i}_DataNascita",
                f"P{i}_ComuneNascita",
                f"P{i}_ProvinciaNascita",
                f"P{i}_StatoNascita",
                f"P{i}_IndirizzoRes",
                f"P{i}_ComuneRes",
                f"P{i}_CAPRes",
                f"P{i}_ProvinciaRes",
                f"P{i}_StatoRes",
            ]
        )

    return columns


AML_TEMPLATE_COLUMNS = build_aml_template_columns()

AML_RAW_FIELDS = {
    # Visura (raw)
    "Denominazione",
    "Partita_IVA",
    "Codice_Fiscale",
    "Numero_REA",
    "Forma_Giuridica",
    "Sede_Legale",
    "CAP",
    "Comune",
    "Provincia",
    "Data_Costituzione",
    "Data_Inizio_Attivita",
    "Codice_ATECO",
    "Attivita_Prevalente",
    "Stato_Attivita",
    # Documento identita (raw)
    "Nome",
    "Cognome",
    "Data_Nascita",
    "Luogo_Nascita",
    "Provincia_Nascita",
    "CF_Persona",
    "Sesso",
    "Residenza",
    "Comune_Residenza",
    "Numero_Documento",
    "Tipo_Documento",
    "Comune_Rilascio",
    "Data_Rilascio",
    "Data_Scadenza",
}


def filter_aml_template_row(row: Dict, max_people: int = 5) -> Dict:
    """Filtra una riga per lasciare solo colonne AML in ordine."""
    columns = build_aml_template_columns(max_people)
    return {col: row.get(col, "") for col in columns}


def filter_aml_raw(data: Dict) -> Dict:
    """Filtra un dizionario di estrazione grezza per campi AML."""
    return {key: value for key, value in data.items() if key in AML_RAW_FIELDS}
