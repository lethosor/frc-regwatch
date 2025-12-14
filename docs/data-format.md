Packed file format
==================

This is the condensed format used to pack data used by the frontend.

* `year`: `int16`: season end year (e.g. `2026` is the 2025-2026 season)
* `n_events`: `int16`: number of events in this file
* repeated `n_events` times:
    * `event_code`: 0-terminated string: alphanumeric event code, lowercase, not including season (e.g. `alhu`)
* `n_teamlists`: `int16`: number of team lists in this file
* repeated `n_teamlists` times:
    * `n_teams`: `int16`: number of teams in this team list
    * repeated `n_teams` times:
        * `team`: `int16`: team number (e.g. `123`)
    * note: index 0 is reserved for the empty team list (no teams)
* `n_snapshots`: `int16`: number of snapshots in this file
* repeated `n_snapshots` times:
    * `timestamp`: `int32`: timestamp of this snapshot, in seconds since `2025-01-01T00:00:00+0000` (to delay Y2K38 issues a while)
    * `n_events`: `int16`: number of events in this snapshot
    * repeated `n_events` times:
        * `event_code_index`: `int16`: index into the event codes array of this event
        * `teamlist_index`: `int16`: index into the team lists array of the team list for this event
