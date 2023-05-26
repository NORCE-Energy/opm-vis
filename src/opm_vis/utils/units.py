"""Unit labels and conversion"""
import warnings

_METRIC = {
    "PRESSURE": "barsa",
    "SGAS": "-",
    "SOIL": "-",
    "SWAT": "-",
    "OIL_DEN": r"kg/m$^3$",
    "GAS_DEN": r"kg/m$^3$",
    "WAT_DEN": r"kg/m$^3$",
    "TEMP": r"$^\circ$C",
    "RS": r"Sm$^3$/Sm$^3$",
    "RSSAT": r"Sm$^3$/Sm$^3$",
    "PORV": r"Rm$^3$",
    "DEPTH": "m",
    "DX": "m",
    "DY": "m",
    "DZ": "m",
    "PERMX": "mD",
    "PERMY": "mD",
    "PERMZ": "mD",
    "PORO": "-",
    "NTG": "-",
    "TRANX": r"cP-Rm$^3$/day/bar",
    "TRANY": r"cP-Rm$^3$/day/bar",
    "TRANZ": r"cP-Rm$^3$/day/bar",
}


_FIELD = {
    "PRESSURE": "psia",
    "SGAS": "-",
    "SOIL": "-",
    "SWAT": "-",
    "OIL_DEN": r"lb/ft$^3$",
    "GAS_DEN": r"lb/ft$^3$",
    "WAT_DEN": r"lb/ft$^3$",
    "TEMP": r"$^\circ$F",
    "RS": "Mscf/stb",
    "RSSAT": "Mscf/stb",
    "PORV": "Rb",
    "DEPTH": "ft",
    "DX": "ft",
    "DY": "ft",
    "DZ": "ft",
    "PERMX": "mD",
    "PERMY": "mD",
    "PERMZ": "mD",
    "PORO": "-",
    "NTG": "-",
    "TRANX": "cP-Rb/day/psi",
    "TRANY": "cP-Rb/day/psi",
    "TRANZ": "cP-Rb/day/psi",
}


_LAB = {
    "PRESSURE": "atma",
    "SGAS": "-",
    "SOIL": "-",
    "SWAT": "-",
    "OIL_DEN": r"g/cm$^3$",
    "GAS_DEN": r"g/cm$^3$",
    "WAT_DEN": r"g/cm$^3$",
    "TEMP": "K",
    "RS": r"Scm$^3$/Scm$^3$",
    "RSSAT": r"Scm$^3$/Scm$^3$",
    "PORV": r"Rm$^3$",
    "DEPTH": "cm",
    "DX": "cm",
    "DY": "cm",
    "DZ": "cm",
    "PERMX": "mD",
    "PERMY": "mD",
    "PERMZ": "mD",
    "PORO": "-",
    "NTG": "-",
    "TRANX": r"cP-Rcm$^3$/hr/atm",
    "TRANY": r"cP-Rcm$^3$/hr/atm",
    "TRANZ": r"cP-Rcm$^3$/hr/atm",
}


_PVT_M = {
    "PRESSURE": "atma",
    "SGAS": "-",
    "SOIL": "-",
    "SWAT": "-",
    "OIL_DEN": r"kg/m$^3$",
    "GAS_DEN": r"kg/m$^3$",
    "WAT_DEN": r"kg/m$^3$",
    "TEMP": r"$^\circ$C",
    "RS": r"Sm$^3$/Sm$^3$",
    "RSSAT": r"Sm$^3$/Sm$^3$",
    "PORV": r"Rm$^3$",
    "DEPTH": "m",
    "DX": "m",
    "DY": "m",
    "DZ": "m",
    "PERMX": "mD",
    "PERMY": "mD",
    "PERMZ": "mD",
    "PORO": "-",
    "NTG": "-",
    "TRANX": r"cP-Rm$^3$/day/atm",
    "TRANY": r"cP-Rm$^3$/day/atm",
    "TRANZ": r"cP-Rm$^3$/day/atm",
}


class Label:
    """
    Unit labels for OPM/Eclipse unit convensions
    """

    def __init__(self, unit_type: str) -> None:
        """
        Initialize by setting unit convension

        Parameters
        ----------
        unit_type : str
            OPM/Eclipse unit conversions: metric, field, lab and pvt-m
        """
        # Internalize input
        self.unit_type = unit_type.lower()

    def __call__(self, mnemonic: str) -> str:
        """
        Lookup unit label for a specific mnemonic and OPM/Eclipse unit convension

        Parameters
        ----------
        mnemonic : str
            Keyword

        Returns
        -------
        label : str
            Unit
        """
        if self.unit_type == "metric":
            label = _METRIC[mnemonic]
        elif self.unit_type == "field":
            label = _FIELD[mnemonic]
        elif self.unit_type == "lab":
            label = _LAB[mnemonic]
        elif self.unit_type == "pvt-m":
            label = _PVT_M[mnemonic]
        else:
            # Warn that mnemonic not found and we set UNKNOWN as label
            warnings.warn(
                f'No label made for "{mnemonic}" yet! The unit label "UNKNOWN" will be given.'
            )
            label = "UNKNOWN"

        return label

    def unit_convension(self) -> str:
        """Return unit conversion"""
        return self.unit_type
