"""Unit labels and conversion"""
import re
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

    def unit_convention(self) -> str:
        """Return unit convention"""
        return self.unit_type


# Summary vectors need none of the convention tables above: .SMSPEC stores a unit string per
# vector, so the file itself says whether a rate is in STB/DAY or SM3/DAY (see
# opm_vis.utils.summary.SummaryReader.unit). Only the rendering is ours - Eclipse spells those
# units in upper-case ASCII, while the rest of opm_vis writes them as Matplotlib mathtext.
_SUMMARY_UNIT_TOKENS = {
    "SM3": r"Sm$^3$",
    "RM3": r"Rm$^3$",
    "M3": r"m$^3$",
    "SCM3": r"Scm$^3$",
    "RCM3": r"Rcm$^3$",
    "CM3": r"cm$^3$",
    "STB": "stb",
    "RB": "Rb",
    "MSCF": "Mscf",
    "SCF": "scf",
    "DAY": "day",
    "DAYS": "days",
    "HOUR": "hour",
    "HOURS": "hours",
    "HR": "hr",
    "YEARS": "years",
    "BARSA": "barsa",
    "BARS": "bar",
    "BAR": "bar",
    "PSIA": "psia",
    "PSI": "psi",
    "ATMA": "atma",
    "ATM": "atm",
    "KG": "kg",
    "LB": "lb",
    "CP": "cP",
    "MD": "mD",
    "DEGC": r"$^\circ$C",
    "DEGF": r"$^\circ$F",
    "M": "m",
    "FT": "ft",
    "CM": "cm",
}

# Written on the axis when .SMSPEC reports an empty unit string, e.g. for a saturation
_DIMENSIONLESS_LABEL = "-"

# Units are built from tokens joined by "/" and "*", e.g. "STB/DAY" or "CP*RM3/DAY/BAR". Keeping
# the separators in the split result is what lets each token be looked up on its own.
_UNIT_SEPARATORS = re.compile(r"([/*])")


def summary_unit_label(unit: str) -> str:
    """
    Render the unit string of a summary vector as a Matplotlib-ready label

    Parameters
    ----------
    unit : str
        Raw unit string from the summary file, as SummaryReader.unit() returns it, e.g.
        "STB/DAY" or "" for a dimensionless vector

    Returns
    -------
    str
        Label to write on an axis, e.g. "stb/day", "Sm$^3$/Sm$^3$" or "-"

    Notes
    -----
    An unrecognised token is passed through unchanged rather than warned about, unlike Label:
    there is no fixed vocabulary here, since user-defined (UDQ) vectors carry whatever unit
    string the deck gave them, so a warning would fire on perfectly valid data.
    """
    unit = unit.strip()
    if not unit:
        return _DIMENSIONLESS_LABEL

    return "".join(
        token if token in "/*" else _SUMMARY_UNIT_TOKENS.get(token.upper(), token)
        for token in _UNIT_SEPARATORS.split(unit)
    )
