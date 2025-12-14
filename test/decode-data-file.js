const fs = require("fs");
const zlib = require("node:zlib");

const TIMESTAMP_BASE = new Date(Date.UTC(2025, 0, 1));

function DataFileReader(data) {
  // accept Uint8Array or ArrayBuffer
  const bytes = data instanceof Uint8Array ? data : new Uint8Array(data);
  const view = new DataView(bytes.buffer);

  let offset = 0;

  function ensure(n) {
    if (offset + n > bytes.length) {
      throw new RangeError(
        `Read past end: need ${n} bytes at offset ${offset}, length ${bytes.length}`,
      );
    }
  }

  return {
    get offset() {
      return offset;
    },

    get length() {
      return bytes.length;
    },

    readInt16() {
      ensure(2);
      const v = view.getInt16(offset, true);
      offset += 2;
      return v;
    },

    readInt32() {
      ensure(4);
      const v = view.getInt32(offset, true);
      offset += 4;
      return v;
    },

    readStr() {
      const start = offset;

      while (offset < bytes.length && bytes[offset] !== 0) {
        offset++;
      }
      if (offset >= bytes.length) {
        throw new RangeError(
          `Unterminated C-string starting at offset ${start}`,
        );
      }

      const slice = bytes.subarray(start, offset);
      offset += 1; // skip terminator

      let out = "";
      for (let i = 0; i < slice.length; i++) {
        out += String.fromCharCode(slice[i]);
      }
      return out;
    },
  };
}

function decodeDataFile(contents) {
  const reader = DataFileReader(contents);
  const out = [];
  const year = reader.readInt16();

  const event_codes = [];
  const num_event_codes = reader.readInt16();
  for (let _ = 0; _ < num_event_codes; _++) {
    event_codes.push(reader.readStr());
  }

  const team_lists = [];
  const num_team_lists = reader.readInt16();
  for (let _ = 0; _ < num_team_lists; _++) {
    const teams = [];
    const num_teams = reader.readInt16();
    for (let _ = 0; _ < num_teams; _++) {
      teams.push(reader.readInt16());
    }
    team_lists.push(teams);
  }

  const num_snapshots = reader.readInt16();
  for (let _ = 0; _ < num_snapshots; _++) {
    const snapshot_time_utc = new Date(
      reader.readInt32() * 1000 + TIMESTAMP_BASE.getTime(),
    );
    const snapshot = {
      timestamp: snapshot_time_utc.getTime() / 1000,
      events: [],
    };
    const num_events = reader.readInt16();
    for (let _ = 0; _ < num_events; _++) {
      const event_code = event_codes[reader.readInt16()];
      const team_list = team_lists[reader.readInt16()];
      snapshot.events.push({
        event_code,
        teams: team_list,
      });
    }
    out.push(snapshot);
  }

  return out;
}

const filePath = process.argv[2];
if (!filePath) throw "missing arg";

process.stdout.write(
  JSON.stringify(decodeDataFile(zlib.gunzipSync(fs.readFileSync(filePath)))),
);
process.stdout.write("\n");
