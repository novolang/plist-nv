#!/usr/bin/env python3
"""Write tests/differential_tests.nv from seeded values, with Python's
plistlib as the oracle.

Each case is a value drawn from a seeded generator.  plistlib writes it
in the XML form and in the binary form, with `sort_keys=False` so that a
dictionary keeps its order, and the script records both files and a
rendering of the value.  The suite asserts that this package reads each
file to that value and writes the value back to the same bytes.

The values cover every kind plistlib writes: booleans, integers of every
width including the sixteen-byte one, reals, strings in ASCII and in
UTF-16, dates, data of lengths that wrap the base64 lines, arrays and
dictionaries nested three deep, and UIDs in the binary form only.  Two
things are left out because plistlib treats them differently from this
package and from Apple's writer: a negative zero, which plistlib stores
once together with zero, and a carriage return in a string, which
plistlib's XML writer turns into a line feed.

Run from the package root:
    python3 tools/differential.py
The output is passed through `novo fmt`.
"""
import datetime
import os
import plistlib
import random
import struct
import subprocess
import sys

SEED = 20260927
CASES = 40
UID_CASES = 8
REF = datetime.datetime(2001, 1, 1)
ALPHABET = list('abcdefghijklmnopqrstuvwxyz ABCXYZ0123456789&<>"\'#$/') + \
    ['é', 'ß', 'ø', '日本', '😀', '\t', '\n', 'Ω']


def gen_str(r):
    return ''.join(r.choice(ALPHABET) for _ in range(r.randint(0, 20)))


def gen_int(r):
    pick = r.randint(0, 7)
    if pick == 0:
        return r.randint(0, 255)
    if pick == 1:
        return r.randint(256, 65535)
    if pick == 2:
        return r.randint(65536, 2**32 - 1)
    if pick == 3:
        return r.randint(2**32, 2**63 - 1)
    if pick == 4:
        return r.randint(-2**63, -1)
    if pick == 5:
        return r.randint(2**63, 2**64 - 1)
    if pick == 6:
        return r.choice([0, 2**63 - 1, -2**63, 2**64 - 1, 2**63])
    return r.randint(-1000, 1000)


def gen_real(r):
    pick = r.randint(0, 4)
    if pick == 0:
        return float(r.randint(-10**6, 10**6))
    if pick == 1:
        return r.choice([1e16, 1.5e17, 1e-7, 0.1, 1e300, 5e-324, 123456789.125])
    if pick == 2:
        return r.uniform(-1e6, 1e6)
    if pick == 3:
        return float(r.randint(1, 9)) * 10.0 ** r.randint(15, 22)
    return r.random()


def gen_scalar(r):
    pick = r.randint(0, 6)
    if pick == 0:
        return r.random() < 0.5
    if pick == 1:
        return gen_int(r)
    if pick == 2:
        return gen_real(r)
    if pick == 3:
        return gen_str(r)
    if pick == 4:
        return REF + datetime.timedelta(seconds=r.randint(-10**9, 10**9))
    return bytes(r.getrandbits(8) for _ in range(r.randint(0, 120)))


def gen(r, depth, uids):
    pick = r.randint(0, 9)
    if depth < 3 and pick < 2:
        return [gen(r, depth + 1, uids) for _ in range(r.randint(0, 5))]
    if depth < 3 and pick < 4:
        d = {}
        for _ in range(r.randint(0, 5)):
            d[gen_str(r)] = gen(r, depth + 1, uids)
        return d
    if uids is not None and pick == 9:
        n = r.randint(0, 70000)
        while n in uids:
            n += 1
        uids.add(n)
        return plistlib.UID(n)
    return gen_scalar(r)


def big_hex(n):
    return n.to_bytes(16, 'big', signed=n < 0).hex()


def shown(v):
    """The rendering the suite's `shown` computes, as Python sees it."""
    if isinstance(v, bool):
        return 'T' if v else 'F'
    if isinstance(v, int):
        if -2**63 <= v < 2**63:
            return 'i%d' % v
        return 'I' + big_hex(v)
    if isinstance(v, float):
        return 'r' + struct.pack('>d', v).hex()
    if isinstance(v, str):
        return 's%d:%s' % (len(v.encode()), v)
    if isinstance(v, datetime.datetime):
        return 'd' + struct.pack('>d', (v - REF).total_seconds()).hex()
    if isinstance(v, bytes):
        return 'x' + v.hex()
    if isinstance(v, plistlib.UID):
        return 'u%d' % v.data
    if isinstance(v, list):
        return '[' + ','.join(shown(x) for x in v) + ']'
    return '{' + ','.join(shown(k) + '=' + shown(x) for k, x in v.items()) + '}'


def nv(text):
    """A novo-lang string literal for `text`."""
    out = []
    for ch in text:
        if ch == '\\':
            out.append('\\\\')
        elif ch == '"':
            out.append('\\"')
        elif ch == '$':
            out.append('\\$')
        elif ch == '\n':
            out.append('\\n')
        elif ch == '\t':
            out.append('\\t')
        else:
            out.append(ch)
    return '"' + ''.join(out) + '"'


def main():
    r = random.Random(SEED)
    both, binary_only = [], []
    for _ in range(CASES):
        v = gen(r, 0, None)
        xml = plistlib.dumps(v, fmt=plistlib.FMT_XML, sort_keys=False).decode()
        binary = plistlib.dumps(v, fmt=plistlib.FMT_BINARY, sort_keys=False).hex()
        assert plistlib.loads(bytes.fromhex(binary)) == v
        both.append((xml, binary, shown(v)))
    while len(binary_only) < UID_CASES:
        v = [gen(r, 1, set()) for _ in range(4)]
        if 'u' not in shown(v):
            continue
        binary = plistlib.dumps(v, fmt=plistlib.FMT_BINARY, sort_keys=False).hex()
        binary_only.append((binary, shown(v)))

    lines = [
        '// differential_tests.nv — seeded values written by Python\'s plistlib',
        '// in both forms, read and written back by this package.',
        '//',
        '// Written by tools/differential.py; do not edit by hand.  Seed %d,' % SEED,
        '// %d values in both forms and %d holding UIDs in the binary form only.' % (CASES, UID_CASES),
        '',
        'use std.test',
        'use std.list',
        'use std.str',
        'use std.bytes',
        'use std.float',
        'use plistbin',
        'use plistxml',
        'use plistfmt',
        '',
        '// A value as text that two values share exactly when they are equal,',
        '// reals and dates by their bits.',
        'fn shown(v: PlistValue) -> Str',
        '    match v',
        '        PlistBool(b)       =>',
        '            if b',
        '                return "T"',
        '            "F"',
        '        PlistInteger(n)    => "i${n}"',
        '        PlistBigInteger(b) => "I" + bytes.to_hex(b)',
        '        PlistReal(f)       => "r" + bits(f)',
        '        PlistString(t)     => shown_str(t)',
        '        PlistDate(t)       => "d" + bits(t)',
        '        PlistData(b)       => "x" + bytes.to_hex(b)',
        '        PlistUid(n)        => "u${n}"',
        '        PlistArray(xs)     => "[" + str.join(list.map(xs, shown), ",") + "]"',
        '        PlistSet(xs)       => "(" + str.join(list.map(xs, shown), ",") + ")"',
        '        PlistDict(es)      => "{" + str.join(list.map(es, shown_entry), ",") + "}"',
        '',
        'fn shown_str(t: Str) -> Str',
        '    "s${str.len(t)}:" + t',
        '',
        'fn shown_entry(e: PlistEntry) -> Str',
        '    shown_str(e.key) + "=" + shown(e.value)',
        '',
        'fn bits(f: Float) -> Str',
        '    bytes.to_hex(bytes.u64_be(float.to_bits(f)))',
        '',
        '// Each value: the XML file, the binary file in hexadecimal, and the',
        '// value shown.',
        'fn both_forms() -> [(Str, Str, Str)]',
        '    [',
    ]
    for xml, binary, s in both:
        lines.append('        (%s,' % nv(xml))
        lines.append('        %s,' % nv(binary))
        lines.append('        %s),' % nv(s))
    lines[-1] = lines[-1][:-1]
    lines += [
        '    ]',
        '',
        '// Each value holding a UID: the binary file in hexadecimal, and the',
        '// value shown.',
        'fn binary_only() -> [(Str, Str)]',
        '    [',
    ]
    for binary, s in binary_only:
        lines.append('        (%s,' % nv(binary))
        lines.append('        %s),' % nv(s))
    lines[-1] = lines[-1][:-1]
    lines += [
        '    ]',
        '',
        'fn hex(t: Str) -> Bytes',
        '    bytes.from_hex(t) ?? bytes.zeros(0)',
        '',
        '@test',
        'fn test_both_forms_read_to_the_value_plistlib_wrote() [io]',
        '    for c in both_forms()',
        '        test.case(c.2)',
        '        match plistxml.read(c.0)',
        '            Ok(v)  => test.assert_eq(shown(v), c.2)',
        '            Err(e) => test.fail(e.message())',
        '        match plistbin.read(hex(c.1))',
        '            Ok(v)  => test.assert_eq(shown(v), c.2)',
        '            Err(e) => test.fail(e.message())',
        '',
        '@test',
        'fn test_both_writers_give_plistlibs_bytes() [io]',
        '    for c in both_forms()',
        '        test.case(c.2)',
        '        match plistbin.read(hex(c.1))',
        '            Err(e) => test.fail(e.message())',
        '            Ok(v)  =>',
        '                match plistxml.write(v)',
        '                    Ok(t)  => test.assert_eq(t, c.0)',
        '                    Err(e) => test.fail(e.message())',
        '                match plistbin.write(v)',
        '                    Ok(b)  => test.assert_eq(bytes.to_hex(b), c.1)',
        '                    Err(e) => test.fail(e.message())',
        '',
        '@test',
        'fn test_a_conversion_is_plistlibs_other_file() [io]',
        '    for c in both_forms()',
        '        test.case(c.2)',
        '        match plistfmt.convert(bytes.from_str(c.0), PlistBinaryForm)',
        '            Ok(b)  => test.assert_eq(bytes.to_hex(b), c.1)',
        '            Err(e) => test.fail(e.message())',
        '        match plistfmt.convert(hex(c.1), PlistXmlForm)',
        '            Ok(b)  => test.assert_eq(bytes.to_str(b), c.0)',
        '            Err(e) => test.fail(e.message())',
        '',
        '@test',
        'fn test_uids_read_and_write_as_plistlib_writes_them() [io]',
        '    for c in binary_only()',
        '        test.case(c.1)',
        '        match plistbin.read(hex(c.0))',
        '            Err(e) => test.fail(e.message())',
        '            Ok(v)  =>',
        '                test.assert_eq(shown(v), c.1)',
        '                match plistbin.write(v)',
        '                    Ok(b)  => test.assert_eq(bytes.to_hex(b), c.0)',
        '                    Err(e) => test.fail(e.message())',
        '',
    ]
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = os.path.join(here, 'tests', 'differential_tests.nv')
    with open(out, 'w') as fh:
        fh.write('\n'.join(lines))
    subprocess.run([os.environ.get('NOVO', 'novo'), 'fmt', out], check=True)
    print('wrote %s: %d + %d cases' % (out, len(both), len(binary_only)))


if __name__ == '__main__':
    sys.exit(main())
