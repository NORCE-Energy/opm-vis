""" FAULTS keyword reader """
from __future__ import annotations

from dataclasses import dataclass

from opm.io.parser import Parser

# Eclipse allows either the I/J/K or the X/Y/Z notation for a fault face direction; normalized to
# X/Y/Z here so callers only ever see one spelling.
_FACE_ALIASES = {
    "I": "X",
    "I-": "X-",
    "J": "Y",
    "J-": "Y-",
    "K": "Z",
    "K-": "Z-",
}


@dataclass(frozen=True)
class FaultFace:
    """
    One IJK box making up part of a fault, i.e. one record of the FAULTS keyword

    Attributes
    ----------
    i1, i2, j1, j2, k1, k2 : int
        0-based, inclusive cell index range the box covers
    face : str
        Direction the fault face points in: 'X', 'X-', 'Y', 'Y-', 'Z', or 'Z-'
    """

    i1: int
    i2: int
    j1: int
    j2: int
    k1: int
    k2: int
    face: str


class FaultReader:
    """
    Reader for the FAULTS keyword, collected from a .DATA file or an include file
    """

    def __init__(self, path: str) -> None:
        """
        Parse a deck file and collect every FAULTS keyword record in it

        Parameters
        ----------
        path : str
            Path to an Eclipse/OPM deck file. This can be a full .DATA file - INCLUDE keywords
            are resolved relative to the including file, exactly as OPM Flow does - or a
            standalone include file that itself just holds FAULTS keyword(s), with no other
            section of the deck present.

        Raises
        ------
        RuntimeError / OSError
            Propagated from opm.io.parser.Parser.parse, e.g. for a missing file or invalid
            Eclipse deck syntax.

        Notes
        -----
        Built on opm.io.parser.Parser - the same deck parser OPM Flow itself uses - rather than
        opm.io.ecl_state.EclipseState. EclipseState.faultNames()/faultFaces() would give already
        resolved fault geometry, but building one needs a full, valid deck (RUNSPEC, a GRID
        section with actual grid geometry, ...), which an arbitrary standalone include file does
        not have. Reading the raw FAULTS records directly works from just the file(s) being read,
        with no assumption about the rest of the deck.
        """
        deck = Parser().parse(path)

        self._faces: dict[str, list[FaultFace]] = {}
        for keyword in deck:
            if keyword.name != "FAULTS":
                continue
            for i in range(len(keyword)):
                record = keyword[i]
                name: str = record[0].get_str(0)
                face: str = record[7].get_str(0)
                self._faces.setdefault(name, []).append(
                    FaultFace(
                        i1=record[1].get_int(0) - 1,
                        i2=record[2].get_int(0) - 1,
                        j1=record[3].get_int(0) - 1,
                        j2=record[4].get_int(0) - 1,
                        k1=record[5].get_int(0) - 1,
                        k2=record[6].get_int(0) - 1,
                        face=_FACE_ALIASES.get(face, face),
                    )
                )

    def names(self) -> list[str]:
        """
        Names of every fault defined by the FAULTS keyword(s)

        Returns
        -------
        list[str]
            Fault names, in the order they were first encountered in the deck
        """
        return list(self._faces)

    def faces(self, name: str) -> list[FaultFace]:
        """
        All face boxes making up one named fault

        Parameters
        ----------
        name : str
            Fault name, as given in the FAULTS keyword

        Returns
        -------
        list[FaultFace]
            One entry per FAULTS record for this fault, in deck order. Records for the same
            fault name accumulate across every occurrence of the FAULTS keyword in the deck
            (including ones pulled in through separate INCLUDE files), matching how Eclipse
            treats repeated FAULTS keywords.

        Raises
        ------
        KeyError
            If name is not a fault defined in the deck
        """
        if name not in self._faces:
            raise KeyError(f"{name} is not a fault defined by FAULTS in this deck!")
        return self._faces[name]

    def has_faults(self) -> bool:
        """
        Whether the deck defines any faults at all

        Returns
        -------
        bool
            True if at least one FAULTS keyword record was found
        """
        return bool(self._faces)
