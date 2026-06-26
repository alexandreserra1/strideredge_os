"""core/parsers/fit_parser.py — parser concreto de arquivos .FIT (Garmin).

Implementa o contrato BaseTelemetryParser usando o garmin-fit-sdk oficial.
Le os "record messages" (uma leitura por segundo) e devolve um DataFrame Polars
com as colunas padronizadas do nosso schema (fact_telemetry).
"""

from pathlib import Path

import polars as pl
from garmin_fit_sdk import Decoder, Stream

from core.framework.interfaces import BaseTelemetryParser

# A Garmin guarda lat/lon como inteiros em "semicirculos", nao em graus.
# Conversao: graus = semicirculos * (180 / 2^31).
SEMICIRCLES_TO_DEGREES = 180.0 / (2**31)


class FitParser(BaseTelemetryParser):
    """Extrai telemetria de um arquivo .FIT para um DataFrame Polars."""

    def validate_file(self) -> bool:
        """Confere se o arquivo existe e passa na checagem de integridade (CRC).

        Usa check_integrity() (valida o CRC do arquivo inteiro) num Stream novo.
        Nao usamos is_fit() porque nesta versao do SDK ele dá falso-negativo em
        arquivos validos; check_integrity() e a garantia mais forte de qualquer jeito.
        """
        if not Path(self.file_path).is_file():
            return False
        stream = Stream.from_file(self.file_path)
        return Decoder(stream).check_integrity()

    def to_dataframe(self) -> pl.DataFrame:
        """Decodifica os record messages e padroniza as colunas."""
        stream = Stream.from_file(self.file_path)
        decoder = Decoder(stream)
        messages, _errors = decoder.read()

        # 'record_mesgs' = lista de dicts, um por leitura temporal. Vazia se nao houver.
        records = messages.get("record_mesgs", [])

        rows = []
        for rec in records:
            lat = rec.get("position_lat")
            lon = rec.get("position_long")
            # Cadencia: o Garmin grava 'cadence' em PASSADAS/min (ciclos, uma perna).
            # Passos/min = (cadence + fractional_cadence) * 2. Validado nos dados:
            # total_strides/tempo == avg_cadence, e distancia/(2*strides) == avg_step_length.
            # (Suposicao de esporte de pe; ciclismo precisaria de tratamento proprio.)
            raw_cad = rec.get("cadence")
            frac_cad = rec.get("fractional_cadence") or 0.0
            cadence_spm = round((raw_cad + frac_cad) * 2) if raw_cad is not None else None
            rows.append({
                "timestamp": rec.get("timestamp"),
                "heart_rate": rec.get("heart_rate"),
                "cadence": cadence_spm,
                # velocidade instantanea em m/s (campo 'enhanced_speed', ja suavizado).
                "speed_ms": rec.get("enhanced_speed"),
                # distancia acumulada em metros (campo 'distance' real do Garmin).
                "distance_m": rec.get("distance"),
                # converte semicirculos -> graus (None continua None).
                "latitude": lat * SEMICIRCLES_TO_DEGREES if lat is not None else None,
                "longitude": lon * SEMICIRCLES_TO_DEGREES if lon is not None else None,
                # prefere a altitude "enhanced" (mais precisa) quando existe.
                "altitude": rec.get("enhanced_altitude", rec.get("altitude")),
                # campos avancados de dinamica de corrida — podem faltar (NULL).
                "vertical_oscillation": rec.get("vertical_oscillation"),
                "stance_time_ms": rec.get("stance_time"),
            })

        return pl.DataFrame(rows)

    def session_metadata(self) -> dict:
        """Le a mensagem de sessao (resumo da atividade calculado pelo relogio).

        Devolve tipo de esporte, distancia, duracao e FC media. Campos ausentes
        viram None. Usado para popular dim_activities sem 'chutar' valores.
        """
        stream = Stream.from_file(self.file_path)
        messages, _errors = Decoder(stream).read()
        sessions = messages.get("session_mesgs", [])
        if not sessions:
            return {}

        s = sessions[0]

        # Zonas de FC calculadas pelo proprio Garmin (resumo da SESSAO inteira).
        # Pegamos o registro time_in_zone com reference_mesg == 'session' (os
        # demais sao por volta/split). Pode faltar (ex: alguns treinos indoor).
        zone_boundaries = None
        zone_seconds = None
        for tiz in messages.get("time_in_zone_mesgs", []):
            if tiz.get("reference_mesg") == "session":
                zone_boundaries = tiz.get("hr_zone_high_boundary")  # ult. = FC max real
                zone_seconds = tiz.get("time_in_hr_zone")           # segundos por faixa
                break

        return {
            "sport": s.get("sport"),                          # ex: 'running', 'training'
            "sub_sport": s.get("sub_sport"),                  # ex: 'generic', 'hiit'
            "start_time": s.get("start_time"),
            "total_distance_meters": s.get("total_distance"),
            "total_duration_seconds": s.get("total_timer_time"),
            "avg_heart_rate": s.get("avg_heart_rate"),
            "hr_zone_boundaries": zone_boundaries,
            "hr_zone_seconds": zone_seconds,
        }
