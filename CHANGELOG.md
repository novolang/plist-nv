# Changelog

All notable changes to plist-nv are recorded here. The format is
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
package follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
with the pre-1.0 rule that a breaking change bumps the MINOR number.

## 0.1.0 — 2026-09-27

The first implementation of the interface published as 0.0.1: both
forms read and written, with the bytes Python's plistlib writes.

### Changed

These change the interface's declarations, so a program written against
0.0.x may need the edits named here.

- `PlistFault` has a `PlistTooLarge(size, most)` variant, which
  `plistbin.read_with` answers for a buffer past `PlistLimits.max_bytes`.
- `PlistLimits` is a `@value` struct.  A changed limit is a new literal.
- `plistvalue.as_cfuid_dict` converts every UID in a tree, at any
  depth, and answers any other value unchanged.
- `plistbin.validate` reads the values as `read` does; it no longer
  claims to build none.
- The dependency is xml-nv `^0.1.0`, and the toolchain floor is 0.13.0.

### Behaviour the interface left open

- The binary writer orders objects as plistlib does, a dictionary's
  keys before its values, stores equal scalars once (UIDs included),
  and never shares an array or a dictionary.  The XML writer uses
  plistlib's layout, including the width of a `<data>` element's base64
  lines at each depth and Python's spelling of a real.  For a value
  plistlib writes with `sort_keys=False`, both files are byte for byte
  plistlib's.
- A string holding a control character other than tab, line feed and
  carriage return is `PlistNoXmlSpelling("control character")` in the
  XML form.  A carriage return is written `&#13;`.
- The binary reader refuses the null object `0x00` and the fill byte
  `0x0F` as `PlistUnknownMarker`, and a dictionary key that is not a
  string as `PlistBadDictShape`.  An object reached by two paths is read
  once.
- The XML reader accepts a `plist` element with no `version`, a
  hexadecimal `integer` after `0x`, a `date` whose later parts are left
  off or that carries a `+hh:mm` offset, and comments and white space
  between elements.  It refuses other text between elements as
  `PlistBadText`.
- An XML `integer` outside the range of `Int` that fits sixteen bytes
  is a `PlistBigInteger`, as the binary form's sixteen-byte integer is.
- `plistxml.date_text` rounds a fractional second towards the earlier
  second.
- `plistbin.marker_kind_name` answers `"unknown"` for a kind the format
  does not assign.
- The API test that converted the one-object file to XML expected
  `<true/>`; that file holds `false`, and the test now says so.

## [0.0.1]

**The interface, published before anyone implements it.** Every public
type and function carries its full signature, its effect row and its
doc comment; every body is `todo()`; the release is recorded
`implemented = false`.

### Added

- `plistbin` — the load-bearing interface, and it is the decision to put
  the TABLES on the surface. A binary property list is a graph: a
  trailer that says how wide its numbers are, an offset table of byte
  offsets, and objects whose collections hold indexes rather than
  elements. A reader that only handed back a value would leave three
  questions unanswerable — is this table sound, how many distinct
  objects are there, and does a file we wrote have the object count
  `plutil` produces — and all three are what somebody debugging a
  property list actually asks. So `read_index` answers the trailer and
  the offset table with no value built, `object_at` reads one object by
  index, and `read` is `read_index` plus the walk. Every number in the
  trailer is checked against the buffer, because a reader that trusted
  it would index wherever it said.
- `plistvalue` — a date is a NUMBER of seconds from the 2001 reference
  instant, and data is BYTES. Both are their own kind rather than a
  string somebody has to recognise, which is the mistake JSON forces on
  everybody. A civil date would have needed a calendar and a zone, and
  this package is `core` with no clock, so `unix_seconds` hands
  calendar-nv the one number it needs. `PlistBigInteger` is a separate
  arm because the binary form has a sixteen-byte width and a reader
  handed `-1` for `2^127 - 1` could not tell it from an actual `-1`.
- The two values with no XML spelling — a set and a UID — are refused by
  name rather than converted. Apple's own tools turn a UID into a
  dictionary with a `CF$UID` key and the value stops being a UID;
  `as_cfuid_dict` is that conversion made deliberate, and
  `xml_blockers` gives the path of every value that blocks a
  conversion so the message names the place and not the kind.
- `plistxml` — over xml-nv, and not over a scanner of this package's
  own. The property list document type is eleven elements with no
  namespaces, and a scanner for it would still have every escaping,
  entity and encoding decision to get wrong beside a package that has
  already made them. `from_document` takes xml-nv's tree so a caller
  that has parsed the file does not parse it twice.
- `plistfmt` — the form is decided by the first bytes and never by the
  file name, because `Info.plist` is XML in one bundle and binary in
  the next.
- `plisterror` — twenty-one reasons with the byte offset each was found
  at, and `is_file_fault` separating "these bytes are malformed" from
  "this value cannot be written that way".

### Known

- `novo test` is red, and that is the release's expected state: every
  assertion in the API suite reaches `not implemented:
  plist-nv.<module>.<fn>`.
- **The XML half cannot be implemented before xml-nv's is.** `^0.0.2`
  pins exactly 0.0.2, which is itself an interface release whose bodies
  are `todo()`. The binary half depends on nothing and can be
  implemented first, and the README says so.
- **`plutil` is named as the oracle but no corpus is generated.** The
  suite carries the smallest documents that show each rule; the
  generated run over an `Info.plist`, a `launchd` job description and
  an `NSKeyedArchiver` archive lands with the implementation.
- **The OpenStep text form is not read**, and `detect` answers
  `PlistUnknownFormat` for it rather than guessing.
- **No `tests/embedded_probe.nv`.** The absence is a claim not made
  rather than a claim skipped: a property list is a tree of owned
  strings and buffers, and xml-nv makes no device claim either.
