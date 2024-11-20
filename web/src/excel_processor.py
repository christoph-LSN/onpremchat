import pandas as pd

class ExcelProcessor:
    def __init__(self, config=None, llm=None):
        """
        Initialisiert den Excel-Prozessor.

        :param config: Konfigurationseinstellungen (optional).
        :param llm: Sprachmodell-Instanz (optional).
        """
        self.config = config
        self.llm = llm

    def process_excel(self, filepath):
        """
        Liest und verarbeitet eine Excel-Datei.

        :param filepath: Pfad zur Excel-Datei.
        :return: DataFrame-Inhalt als String oder Fehlernachricht.
        """
        try:
            df = pd.read_excel(filepath)
            # Optional: Übersichten erstellen
            summary = self.summarize_excel(df)
            return summary
        except Exception as e:
            return f"Fehler beim Verarbeiten der Excel-Datei: {str(e)}"

    def summarize_excel(self, df):
        """
        Erstellt eine kurze Übersicht des DataFrames.

        :param df: DataFrame.
        :return: Zusammenfassung als String.
        """
        try:
            summary = {
                "Spalten": df.columns.tolist(),
                "Zeilenanzahl": len(df),
                "Spaltenanzahl": len(df.columns),
                "Erste Zeilen": df.head().to_string(index=False)
            }
            summary_text = (
                f"Zeilenanzahl: {summary['Zeilenanzahl']}\n"
                f"Spaltenanzahl: {summary['Spaltenanzahl']}\n"
                f"Spalten: {', '.join(summary['Spalten'])}\n"
                f"Erste Zeilen:\n{summary['Erste Zeilen']}"
            )
            return summary_text
        except Exception as e:
            return f"Fehler bei der Erstellung der Zusammenfassung: {str(e)}"
