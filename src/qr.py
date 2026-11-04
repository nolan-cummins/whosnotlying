"""
Standard-compliant QR Code generator (ISO/IEC 18004).
Generates scannable QR Code matrices and SVG vector images.
Supports the official 'qrcode' package when available with robust pure-python fallback.
"""

from typing import List, Tuple, Optional


# GF(256) tables with primitive polynomial 0x11D (x^8 + x^4 + x^3 + x^2 + 1)
EXP_TABLE = [0] * 512
LOG_TABLE = [0] * 256
val = 1
for i in range(255):
    EXP_TABLE[i] = val
    EXP_TABLE[i + 255] = val
    LOG_TABLE[val] = i
    val = (val << 1) ^ (0x11D if (val & 0x80) else 0)


def gf_mul(x: int, y: int) -> int:
    if x == 0 or y == 0:
        return 0
    return EXP_TABLE[LOG_TABLE[x] + LOG_TABLE[y]]


def rs_generator_poly(ec_count: int) -> List[int]:
    """
    Generates Reed-Solomon generator polynomial g(x) = prod_{i=0}^{n-1} (x - alpha^i).
    Returned in high-to-low degree order: [1, g_1, g_2, ..., g_n]
    """
    g = [1]
    for i in range(ec_count):
        new_g = [0] * (len(g) + 1)
        for j, coeff in enumerate(g):
            new_g[j] ^= coeff
            new_g[j + 1] ^= gf_mul(coeff, EXP_TABLE[i])
        g = new_g
    return g


def rs_encode(data: List[int], ec_count: int) -> List[int]:
    """Calculates error correction codewords via polynomial division over GF(256)."""
    gen = rs_generator_poly(ec_count)
    res = [0] * ec_count
    for byte in data:
        factor = byte ^ res[0]
        res = res[1:] + [0]
        if factor != 0:
            for j in range(ec_count):
                res[j] ^= gf_mul(gen[j + 1], factor)
    return res


# Version specs: (total_codewords, data_codewords, ec_codewords, [alignment_coords])
VERSION_SPECS = {
    (1, 'L'): (26, 19, 7, []),
    (1, 'M'): (26, 16, 10, []),
    (2, 'L'): (44, 34, 10, [18]),
    (2, 'M'): (44, 28, 16, [18]),
    (3, 'L'): (70, 55, 15, [22]),
    (3, 'M'): (70, 44, 26, [22]),
    (4, 'L'): (100, 80, 20, [26]),
    (4, 'M'): (100, 64, 36, [26]),
    (5, 'L'): (134, 108, 26, [30]),
    (5, 'M'): (134, 86, 48, [30]),
}

# Standard 15-bit format info values for Error Correction 'L' and 'M' (masked with 0x5412)
FORMAT_INFO = {
    ('L', 0): 0x77C4, ('L', 1): 0x72F3, ('L', 2): 0x7DAA, ('L', 3): 0x789D,
    ('L', 4): 0x662F, ('L', 5): 0x6318, ('L', 6): 0x6C41, ('L', 7): 0x6976,
    ('M', 0): 0x5412, ('M', 1): 0x5125, ('M', 2): 0x5E7C, ('M', 3): 0x5B4B,
    ('M', 4): 0x45F9, ('M', 5): 0x40CE, ('M', 6): 0x4F97, ('M', 7): 0x4AA0,
}


class QRCode:
    def __init__(self, data: str, ec_level: str = 'M'):
        self.raw_data = data.encode('utf-8')
        self.ec_level = ec_level
        self.version = self._choose_version(len(self.raw_data), ec_level)
        self.size = 17 + 4 * self.version
        self.modules: List[List[Optional[bool]]] = [[None] * self.size for _ in range(self.size)]
        self.is_function: List[List[bool]] = [[False] * self.size for _ in range(self.size)]
        self._build()

    def _choose_version(self, data_len: int, ec: str) -> int:
        for v in range(1, 6):
            if (v, ec) in VERSION_SPECS:
                _, max_data, _, _ = VERSION_SPECS[(v, ec)]
                # Byte mode overhead: 4 bits mode + 8 bits count = 12 bits -> ~2 bytes
                if data_len + 2 <= max_data:
                    return v
        return 5

    def _build(self):
        self._place_finder_patterns()
        self._place_separators()
        self._place_alignment_patterns()
        self._place_timing_patterns()
        self._place_dark_module()
        self._reserve_format_areas()

        # Generate data and error correction
        data_bytes = self._generate_data_codewords()
        ec_bytes = self._generate_ec_codewords(data_bytes)
        all_bytes = data_bytes + ec_bytes

        # Convert to bit list
        bits = []
        for b in all_bytes:
            for shift in range(7, -1, -1):
                bits.append((b >> shift) & 1)

        # Place data bits in 2-column zig-zag
        self._place_data_bits(bits)

        # Select best mask from 0..7 based on ISO penalties
        self._select_best_mask()

    def _set_module(self, r: int, c: int, val: bool, is_func: bool = False):
        if 0 <= r < self.size and 0 <= c < self.size:
            self.modules[r][c] = val
            if is_func:
                self.is_function[r][c] = True

    def _place_finder(self, top: int, left: int):
        for r in range(7):
            for c in range(7):
                is_black = (r in (0, 6) or c in (0, 6) or (2 <= r <= 4 and 2 <= c <= 4))
                self._set_module(top + r, left + c, is_black, is_func=True)

    def _place_finder_patterns(self):
        self._place_finder(0, 0)
        self._place_finder(0, self.size - 7)
        self._place_finder(self.size - 7, 0)

    def _place_separators(self):
        for i in range(8):
            self._set_module(7, i, False, is_func=True)
            self._set_module(i, 7, False, is_func=True)
            self._set_module(7, self.size - 8 + i, False, is_func=True)
            self._set_module(i, self.size - 8, False, is_func=True)
            self._set_module(self.size - 8, i, False, is_func=True)
            self._set_module(self.size - 8 + i, 7, False, is_func=True)

    def _place_alignment_patterns(self):
        _, _, _, coords = VERSION_SPECS.get((self.version, self.ec_level), (0, 0, 0, []))
        for r in coords:
            for c in coords:
                if self.is_function[r][c]:
                    continue
                for dr in range(-2, 3):
                    for dc in range(-2, 3):
                        is_black = (abs(dr) == 2 or abs(dc) == 2 or (dr == 0 and dc == 0))
                        self._set_module(r + dr, c + dc, is_black, is_func=True)

    def _place_timing_patterns(self):
        for i in range(8, self.size - 8):
            color = (i % 2 == 0)
            if not self.is_function[6][i]:
                self._set_module(6, i, color, is_func=True)
            if not self.is_function[i][6]:
                self._set_module(i, 6, color, is_func=True)

    def _place_dark_module(self):
        self._set_module(4 * self.version + 9, 8, True, is_func=True)

    def _reserve_format_areas(self):
        for i in range(9):
            if not self.is_function[8][i]:
                self.is_function[8][i] = True
            if not self.is_function[i][8]:
                self.is_function[i][8] = True
        for i in range(self.size - 8, self.size):
            if not self.is_function[8][i]:
                self.is_function[8][i] = True
            if not self.is_function[i][8]:
                self.is_function[i][8] = True

    def _generate_data_codewords(self) -> List[int]:
        _, max_data, _, _ = VERSION_SPECS[(self.version, self.ec_level)]
        data_len = len(self.raw_data)

        bit_buf = 0
        bit_len = 0
        bytes_out = []

        def push_bits(value: int, count: int):
            nonlocal bit_buf, bit_len, bytes_out
            bit_buf = (bit_buf << count) | value
            bit_len += count
            while bit_len >= 8:
                bit_len -= 8
                bytes_out.append((bit_buf >> bit_len) & 0xFF)

        push_bits(0b0100, 4)  # Byte mode
        push_bits(data_len, 8)  # Character count
        for b in self.raw_data:
            push_bits(b, 8)

        # Terminator up to 4 bits
        needed_terminator = min(4, (max_data * 8) - (len(bytes_out) * 8 + bit_len))
        if needed_terminator > 0:
            push_bits(0, needed_terminator)

        # Pad to byte boundary
        if bit_len > 0:
            push_bits(0, 8 - bit_len)

        # Pad bytes 0xEC, 0x11
        pad_bytes = [0xEC, 0x11]
        pad_idx = 0
        while len(bytes_out) < max_data:
            bytes_out.append(pad_bytes[pad_idx])
            pad_idx ^= 1

        return bytes_out

    def _generate_ec_codewords(self, data: List[int]) -> List[int]:
        _, _, ec_count, _ = VERSION_SPECS[(self.version, self.ec_level)]
        return rs_encode(data, ec_count)

    def _place_data_bits(self, bits: List[int]):
        bit_idx = 0
        row = self.size - 1
        col = self.size - 1
        dir_up = True

        while col > 0:
            if col == 6:
                col -= 1

            for c_offset in range(2):
                curr_c = col - c_offset
                if not self.is_function[row][curr_c]:
                    if bit_idx < len(bits):
                        self.modules[row][curr_c] = bool(bits[bit_idx])
                        bit_idx += 1
                    else:
                        self.modules[row][curr_c] = False

            if dir_up:
                if row == 0:
                    dir_up = False
                    col -= 2
                else:
                    row -= 1
            else:
                if row == self.size - 1:
                    dir_up = True
                    col -= 2
                else:
                    row += 1

    @staticmethod
    def _mask_condition(mask: int, r: int, c: int) -> bool:
        if mask == 0:
            return (r + c) % 2 == 0
        elif mask == 1:
            return r % 2 == 0
        elif mask == 2:
            return c % 3 == 0
        elif mask == 3:
            return (r + c) % 3 == 0
        elif mask == 4:
            return ((r // 2) + (c // 3)) % 2 == 0
        elif mask == 5:
            return ((r * c) % 2) + ((r * c) % 3) == 0
        elif mask == 6:
            return (((r * c) % 2) + ((r * c) % 3)) % 2 == 0
        elif mask == 7:
            return (((r * c) % 3) + ((r + c) % 2)) % 2 == 0
        return False

    def _apply_mask(self, mask: int):
        for r in range(self.size):
            for c in range(self.size):
                if not self.is_function[r][c]:
                    if self._mask_condition(mask, r, c):
                        self.modules[r][c] = not self.modules[r][c]

    def _penalty_score(self) -> int:
        size = self.size
        penalty = 0

        # Feature 1: Runs of 5+ consecutive same-colored modules
        for r in range(size):
            run = 0
            prev = None
            for c in range(size):
                v = self.modules[r][c]
                if v == prev:
                    run += 1
                else:
                    if run >= 5:
                        penalty += 3 + (run - 5)
                    run = 1
                    prev = v
            if run >= 5:
                penalty += 3 + (run - 5)

        for c in range(size):
            run = 0
            prev = None
            for r in range(size):
                v = self.modules[r][c]
                if v == prev:
                    run += 1
                else:
                    if run >= 5:
                        penalty += 3 + (run - 5)
                    run = 1
                    prev = v
            if run >= 5:
                penalty += 3 + (run - 5)

        # Feature 2: 2x2 blocks of same color
        for r in range(size - 1):
            for c in range(size - 1):
                if self.modules[r][c] == self.modules[r][c + 1] == self.modules[r + 1][c] == self.modules[r + 1][c + 1]:
                    penalty += 3

        # Feature 3: Finder-like patterns 1:1:3:1:1
        pat1 = [True, False, True, True, True, False, True, False, False, False, False]
        pat2 = [False, False, False, False, True, False, True, True, True, False, True]
        for r in range(size):
            for c in range(size - 10):
                sl = [self.modules[r][c + k] for k in range(11)]
                if sl == pat1 or sl == pat2:
                    penalty += 40
        for c in range(size):
            for r in range(size - 10):
                sl = [self.modules[r + k][c] for k in range(11)]
                if sl == pat1 or sl == pat2:
                    penalty += 40

        # Feature 4: Proportion of dark modules
        dark = sum(self.modules[r][c] for r in range(size) for c in range(size))
        ratio = (dark * 100) // (size * size)
        k = abs(ratio - 50) // 5
        penalty += k * 10

        return penalty

    def _select_best_mask(self) -> int:
        best_mask = 0
        best_score = float('inf')

        orig = [[self.modules[r][c] for c in range(self.size)] for r in range(self.size)]

        for mask in range(8):
            for r in range(self.size):
                for c in range(self.size):
                    self.modules[r][c] = orig[r][c]
            self._apply_mask(mask)
            self._place_format_info(mask)
            score = self._penalty_score()
            if score < best_score:
                best_score = score
                best_mask = mask

        for r in range(self.size):
            for c in range(self.size):
                self.modules[r][c] = orig[r][c]
        self._apply_mask(best_mask)
        self._place_format_info(best_mask)
        return best_mask

    def _place_format_info(self, mask: int):
        """Places 15 format bits in the exact ISO/IEC 18004 standard sequence."""
        fmt = FORMAT_INFO.get((self.ec_level, mask), 0x77C4)

        top_left_coords = [
            (8, 0), (8, 1), (8, 2), (8, 3), (8, 4), (8, 5), (8, 7), (8, 8),
            (7, 8), (5, 8), (4, 8), (3, 8), (2, 8), (1, 8), (0, 8)
        ]

        split_coords = [
            (self.size - 1, 8), (self.size - 2, 8), (self.size - 3, 8), (self.size - 4, 8),
            (self.size - 5, 8), (self.size - 6, 8), (self.size - 7, 8),
            (8, self.size - 8), (8, self.size - 7), (8, self.size - 6), (8, self.size - 5),
            (8, self.size - 4), (8, self.size - 3), (8, self.size - 2), (8, self.size - 1)
        ]

        for i in range(15):
            bit = bool((fmt >> (14 - i)) & 1)
            r1, c1 = top_left_coords[i]
            self.modules[r1][c1] = bit
            r2, c2 = split_coords[i]
            self.modules[r2][c2] = bit

    def to_svg(self, box_size: int = 12, border: int = 4, fill: str = "#000000", bg: str = "#ffffff") -> str:
        """Returns standard SVG with mandatory 4-module quiet zone for iPhone camera recognition."""
        dim = (self.size + border * 2) * box_size
        path_data = []

        for r in range(self.size):
            for c in range(self.size):
                if self.modules[r][c]:
                    x = (c + border) * box_size
                    y = (r + border) * box_size
                    path_data.append(f"M{x},{y}h{box_size}v{box_size}h-{box_size}z")

        combined_path = " ".join(path_data)
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {dim} {dim}" width="{dim}" height="{dim}" shape-rendering="crispEdges">\n'
            f'  <rect width="100%" height="100%" fill="{bg}"/>\n'
            f'  <path d="{combined_path}" fill="{fill}"/>\n'
            f'</svg>'
        )


# Detective hat + glasses (the homepage's liars.svg), 24x24 stroke icon.
LOGO_24 = '<path d="M3 10h18"/><path d="M6 10l2-6h8l2 6"/><circle cx="8" cy="15" r="3"/><circle cx="16" cy="15" r="3"/><path d="M11 15h2"/>'


def generate_qr_svg(content: str, box_size: int = 12, border: int = 4, fill: str = "#000000", bg: str = "#ffffff", logo: str = "") -> str:
    """
    Generates standard-compliant QR Code SVG.
    Uses official qrcode package when available with Error Correction Level M (~15% redundancy)
    for reliable scanning on iPhone Camera and Android devices.
    bg="" leaves the background transparent. `logo` (24x24 stroke-icon markup) is drawn in a
    cleared centre square; that switches to level H (~30%) so the hidden modules are recoverable.
    """
    matrix = None
    try:
        import qrcode
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_H if logo else qrcode.constants.ERROR_CORRECT_M,
            box_size=box_size,
            border=border
        )
        qr.add_data(content)
        qr.make(fit=True)
        matrix = qr.modules
    except Exception:
        pass

    if matrix is None:
        qr = QRCode(content, ec_level='M')
        matrix = qr.modules
        logo = ""  # fallback encoder is level M only: not enough redundancy to cover modules

    size = len(matrix)
    hole = range(0)
    if logo:
        n = int(size * 0.26) | 1  # odd, so it centres on a module (~7% of modules hidden)
        lo = (size - n) // 2
        hole = range(lo, lo + n)

    dim = (size + border * 2) * box_size
    path_data = []

    for r in range(size):
        for c in range(size):
            if matrix[r][c] and not (r in hole and c in hole):
                x = (c + border) * box_size
                y = (r + border) * box_size
                path_data.append(f"M{x},{y}h{box_size}v{box_size}h-{box_size}z")

    combined_path = " ".join(path_data)
    mark = ""
    if logo:
        side = (len(hole) - 1) * box_size  # leave half a module of clearance on each side
        at = (hole.start + border) * box_size + box_size / 2
        mark = (f'  <g transform="translate({at},{at}) scale({side / 24})" fill="none" stroke="{fill}" stroke-width="2.2" '
                f'stroke-linecap="round" stroke-linejoin="round" shape-rendering="geometricPrecision">{logo}</g>\n')
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {dim} {dim}" width="{dim}" height="{dim}" shape-rendering="crispEdges">\n'
        + (f'  <rect width="100%" height="100%" fill="{bg}"/>\n' if bg else '')
        + f'  <path d="{combined_path}" fill="{fill}"/>\n'
        + mark
        + f'</svg>'
    )
