# plist-nv

A property list is Apple's format for a small tree of configuration
data. It is what an application bundle's `Info.plist` holds, what
`launchd` reads a job description out of, and what `defaults` writes
user preferences into. Its two current forms — XML and binary — are
described by Apple's
[Property List Programming Guide](https://developer.apple.com/library/archive/documentation/Cocoa/Conceptual/PropertyLists/Introduction/Introduction.html)
and by the `CFBinaryPlist.c` source in CoreFoundation. This package
reads and writes both in novo-lang.

## What a property list is

A property list is one value. That value is a boolean, an integer, a
real number, a string, a date, a buffer of raw bytes, an array of
values, or a dictionary of string keys to values. There is no other
kind, and there is no schema.

The **XML form** is a small document type: an `<?xml?>` declaration, an
Apple DOCTYPE, and a `<plist version="1.0">` element holding exactly one
value. Eleven element names exist: `plist`, `dict`, `key`, `array`,
`string`, `integer`, `real`, `data`, `date`, `true`, `false`. A date is
ISO 8601 text and a data buffer is base64 text.

The **binary form** begins with the eight bytes `bplist00` and ends with
a thirty-two-byte **trailer**. The trailer is read first, because
everything else is reached through it.

| Trailer bytes | Meaning |
| --- | --- |
| 0–5 | unused |
| 6 | the width in bytes of one entry in the offset table |
| 7 | the width in bytes of one object reference |
| 8–15 | how many objects the file holds |
| 16–23 | which object is the root |
| 24–31 | where the offset table starts |

The **offset table** is that many entries of that width, each the byte
offset of one object. An **object** is a marker byte — four bits of kind
and four of length or width — and its payload. A collection's payload is
not its elements: it is their *indexes* into the offset table. So the
same string written into ten dictionaries is stored once, and a binary
property list is a graph rather than a tree.

The binary form has two kinds of value the XML document type has no word
for: a **set**, and a **UID**, which is how `NSKeyedArchiver` points from
one archived object to another.

A property list **date** is an instant, counted in seconds from
2001-01-01 00:00:00 UTC, which Apple calls the reference date. The
binary form stores it as a 64-bit float and the XML form writes it as
ISO 8601.

## Install

```
novo pkg add plist-nv
```

## Example

```novo
use std.bytes
use plistfmt
use plistvalue
use plistbin

fn main() [io]
    // The bytes of a .plist file, which the caller read from disk. The
    // file's name does not say which form it is in; its first bytes do.
    let raw = bytes.from_str("bplist00")

    match plistfmt.read(raw)
        Err(e) => println("not a property list: ${e.message()}")
        Ok(root) =>
            // Walk to one value by its dictionary keys.
            match plistvalue.path(root, ["CFBundleName"])
                None    => println("no CFBundleName")
                Some(v) =>
                    match plistvalue.as_str(v)
                        Err(e) => println(e.message())
                        Ok(s)  => println(s)

            // Convert it to XML, which refuses if the file held a set
            // or a UID — neither has a spelling in that document type.
            match plistfmt.write(root, PlistXmlForm)
                Err(e) => println("cannot write as XML: ${e.message()}")
                Ok(b)  => println(bytes.to_str(b))

    // The binary form's own tables, without building any value.
    match plistbin.read_index(raw)
        Err(e) => println(e.message())
        Ok(ix) => println("${ix.object_count} object(s)")
```

Build and test with `novo pkg build` and `novo test tests/`.

## What the package contains

| Module | Contents |
| --- | --- |
| `plisterror` | Every refusal, with the byte offset it was found at. |
| `plistvalue` | The ten kinds of value, the dictionary that keeps its order, and the conversions a date needs. |
| `plistbin` | The binary form, with its trailer and its offset table on the surface. |
| `plistxml` | The XML form, read through xml-nv's tree and written back. |
| `plistfmt` | Which form a buffer is in, and the one call that reads either. |

## How to choose an entry point

**`plistfmt.read` takes a buffer and works out which form it is.** It is
what a tool that opens a file it did not write should use.

**`plistbin.read_index` answers the trailer and the offset table and
builds nothing.** Use it to check a file, to count its objects, or to
show its object graph.

**`plistbin.object_at` reads one object by its index.** A UID is an
index into exactly that table, so this is how an `NSKeyedArchiver`
archive is followed.

**`plistxml.from_document` takes a tree xml-nv has already built.** Use
it for a property list embedded inside a larger XML document, such as a
provisioning profile.

**`plistfmt.convert` is `plutil -convert`.** It reads whichever form it
is given and writes the one asked for, and it refuses rather than losing
a set or a UID on the way to XML.

## The rules a user needs

1. **The form is decided by the first bytes, never by the file name.**
   `Info.plist` is XML in one application bundle and binary in the next.
2. **A date is a number, not a string and not a civil date.** It is
   seconds from 2001-01-01 00:00:00 UTC, and it may be negative.
   `plistvalue.unix_seconds` moves it to the epoch everything else
   counts from; turning it into a calendar date is another package's
   work.
3. **The XML form writes a date with whole seconds only.** The binary
   form's float has a fractional part and the document type has nowhere
   to put it, so that part is lost on conversion to XML.
4. **Data is bytes.** The XML form's base64 is decoded on reading and
   encoded on writing, so no caller has to guess which strings were
   really buffers.
5. **A set and a UID have no XML spelling.** Writing one as XML is
   `PlistNoXmlSpelling`, naming the kind. So is a string holding a
   control character other than tab, line feed and carriage return,
   which XML 1.0 cannot write. A carriage return is written `&#13;`.
   `plistvalue.xml_blockers` gives the path of every value that blocks
   a conversion, so the message can name the place.
6. **`plistvalue.as_cfuid_dict` is the deliberate loss.** Apple's own
   tools turn a UID into a dictionary with a `CF$UID` key, and the
   value stops being a UID. That conversion is a call somebody writes,
   not something the writer does quietly.
7. **A dictionary keeps its order and may repeat a key.** Nothing here
   sorts. `plistvalue.get` answers the first entry with a key and
   `plistvalue.count_of` finds the duplicate.
8. **An integer too wide for sixty-four bits is its own kind.**
   `PlistBigInteger` carries the sixteen bytes, and
   `plistvalue.as_int` refuses it rather than truncating.
9. **The binary form is a graph and a graph can have a cycle.** Nothing
   in the format forbids an array whose element refers back to it. The
   reader answers `PlistCycle`.
10. **Every number in the trailer is checked against the buffer.** An
    offset table starting past the end, an object count the table
    cannot hold, a root outside the table and an offset inside the
    trailer are four separate refusals.
11. **The writer stores equal objects once.** Two identical strings,
    integers, dates or buffers anywhere in the tree become one object
    with two references, as Apple's writer and Python's plistlib store
    them. Arrays and dictionaries are never shared.
    `plistbin.write_unshared` is the form that does not, for a test or
    a comparison that wants a predictable table.
12. **The writers produce Python's plistlib's bytes.** The objects are
    in the order plistlib writes them, the trailer's widths are the
    smallest that hold the file's numbers, and the XML layout is one
    element per line with a tab per level. For a value written with
    plistlib's `sort_keys=False`, both files are byte for byte the
    same.
13. **A `<dict>`'s children must alternate `<key>` and a value.** The
    document type cannot express that rule, so every reader checks it
    by hand and this one answers `PlistBadDictShape`.
14. **Only `bplist00` is read.** A later binary version is a format
    with different table widths, and reading it as this one would read
    the wrong bytes.
15. **A UTF-16 string in the binary form comes back as UTF-8.** The
    writer uses the ASCII marker when every character is ASCII and
    UTF-16 otherwise, as Apple's writer does.
16. **The reader is bounded.** `plistbin.PlistLimits` sets the largest
    buffer, the most objects and the deepest nesting it accepts; the
    defaults are 64 MiB, a million objects and sixty-four levels. An
    object reached by two paths is read once.

## What is not included

- **The OpenStep text form**, the `{ key = value; }` syntax that
  predates both of these. It is a different grammar, no current tool
  writes it, and a reader that half-understood it would be worse than
  one that says so. `plistfmt.detect` answers `PlistUnknownFormat`.
- **`NSKeyedArchiver`.** An archive is a property list whose dictionary
  has `$objects`, `$top` and a class table, and unpacking it into
  objects is a layer above this one. What this package gives that layer
  is `PlistUid` and `plistbin.object_at`.
- **A calendar.** See rule 2.
- **Reading the file.** Opening a path costs `[fs]`. The caller reads
  the bytes and hands them over.
- **Preference domains.** `defaults read` merges several files and a
  running daemon's state. This reads one file.
- **A schema.** A property list has no types beyond its ten kinds, and
  checking that an `Info.plist` has the keys a bundle needs is the
  bundle format's business.

## Related packages

- [xml-nv](https://novo-lang.org/packages/xml-nv) reads the XML form.
  This package depends on it, and `plistxml.from_document` takes its
  tree directly.
- [base64-nv](https://novo-lang.org/packages/base64-nv) is the encoding
  a `<data>` element is written in.
- [calendar-nv](https://novo-lang.org/packages/calendar-nv) turns the
  seconds a date holds into a civil date.
- [bson-nv](https://novo-lang.org/packages/bson-nv) and
  [cbor-nv](https://novo-lang.org/packages/cbor-nv) are the other two
  binary document formats on this registry. Both are self-describing
  streams; the binary property list is a graph with a table, which is
  why its reader looks so different.
- [toml-nv](https://novo-lang.org/packages/toml-nv) is the
  configuration format to reach for when the file is yours to choose.

## Test vectors

The normative sources are Apple's Property List Programming Guide for
the value model and the XML document type, the `PropertyList-1.0.dtd`
that every XML property list names, and CoreFoundation's
`CFBinaryPlist.c` for the markers, the tables and the trailer.

The oracle is Python's `plistlib`. `tools/differential.py` draws
seeded values of every kind plistlib writes, has plistlib write each in
both forms, and writes `tests/differential_tests.nv`. The suite asserts
that this package reads both files to the same value, writes the value
back to the same XML text and the same binary bytes, and converts each
file into the other.

```bash
novo test tests/differential_tests.nv   #  4 tests: 40 seeded values and 8 with UIDs
novo test tests/plist_tests.nv          # 25 tests: the two forms, the tables, the values
novo test tests/plistbin_tests.nv       #  9 tests: the binary form's refusals and corners
novo test tests/plistxml_tests.nv       #  8 tests: the XML form's refusals, integers and dates
novo test tests/plistvalue_tests.nv     #  4 tests: the accessors and every fault
bash tests/coverage.sh                  # line coverage over src/
```

The suites also assert that the form is decided by the first bytes,
that every number in the trailer is checked against the buffer, that a
cycle and a reference outside the table are refused, that a `<dict>`
whose children do not alternate is refused, that a UID and a set are
refused by name when written as XML and that this is not a file fault,
and that an integer too wide for sixty-four bits is its own kind in
both forms.

## Licence

Apache-2.0. See `LICENSE`.

<!-- docs/writing-a-readme.md is the style guide for this page. -->
