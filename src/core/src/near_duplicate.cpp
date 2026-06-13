#include "matchycore/near_duplicate.hpp"
#include <array>
#include <cstring>
#include "matchycore/scoring.hpp"

namespace matchycore::near_duplicate
{ namespace
 { // Minimal BLAKE2b (RFC 7693), unkeyed, parameterized digest length. Needed because Python's
  // hashlib.blake2b(digest_size=8) bakes the digest length into the parameter block, so the
  // result differs from any truncation of blake2b-512.
  constexpr std::array<std::uint64_t, 8> kIv =
  { 0x6a09e667f3bcc908ULL, 0xbb67ae8584caa73bULL, 0x3c6ef372fe94f82bULL, 0xa54ff53a5f1d36f1ULL,
    0x510e527fade682d1ULL, 0x9b05688c2b3e6c1fULL, 0x1f83d9abfb41bd6bULL, 0x5be0cd19137e2179ULL };

  constexpr std::uint8_t kSigma[12][16] =
  { {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15},
    {14, 10, 4, 8, 9, 15, 13, 6, 1, 12, 0, 2, 11, 7, 5, 3},
    {11, 8, 12, 0, 5, 2, 15, 13, 10, 14, 3, 6, 7, 1, 9, 4},
    {7, 9, 3, 1, 13, 12, 11, 14, 2, 6, 5, 10, 4, 0, 15, 8},
    {9, 0, 5, 7, 2, 4, 10, 15, 14, 1, 11, 12, 6, 8, 3, 13},
    {2, 12, 6, 10, 0, 11, 8, 3, 4, 13, 7, 5, 15, 14, 1, 9},
    {12, 5, 1, 15, 14, 13, 4, 10, 0, 7, 6, 3, 9, 2, 8, 11},
    {13, 11, 7, 14, 12, 1, 3, 9, 5, 0, 15, 4, 8, 6, 2, 10},
    {6, 15, 14, 9, 11, 3, 0, 8, 12, 2, 13, 7, 1, 4, 10, 5},
    {10, 2, 8, 4, 7, 6, 1, 5, 15, 11, 9, 14, 3, 12, 13, 0},
    {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15},
    {14, 10, 4, 8, 9, 15, 13, 6, 1, 12, 0, 2, 11, 7, 5, 3} };

  std::uint64_t RotR(std::uint64_t value, unsigned bits) { return (value >> bits) | (value << (64 - bits)); }

  void Mix(std::array<std::uint64_t, 16> &v, int a, int b, int c, int d, std::uint64_t x, std::uint64_t y)
  { v[a] = v[a] + v[b] + x;
   v[d] = RotR(v[d] ^ v[a], 32);
   v[c] = v[c] + v[d];
   v[b] = RotR(v[b] ^ v[c], 24);
   v[a] = v[a] + v[b] + y;
   v[d] = RotR(v[d] ^ v[a], 16);
   v[c] = v[c] + v[d];
   v[b] = RotR(v[b] ^ v[c], 63);
  }

  void Compress(std::array<std::uint64_t, 8> &h, const std::uint8_t *block, std::uint64_t bytes_so_far, bool final)
  { std::array<std::uint64_t, 16> m{}, v{};
   for (int i = 0; i < 16; i += 1) std::memcpy(&m[static_cast<std::size_t>(i)], block + i * 8, 8);
   for (int i = 0; i < 8; i += 1)
   { v[static_cast<std::size_t>(i)] = h[static_cast<std::size_t>(i)];
    v[static_cast<std::size_t>(i + 8)] = kIv[static_cast<std::size_t>(i)];
   }
   v[12] ^= bytes_so_far;
   if (final) v[14] = ~v[14];
   for (int round = 0; round < 12; round += 1)
   { const std::uint8_t *s = kSigma[round];
    Mix(v, 0, 4, 8, 12, m[s[0]], m[s[1]]);
    Mix(v, 1, 5, 9, 13, m[s[2]], m[s[3]]);
    Mix(v, 2, 6, 10, 14, m[s[4]], m[s[5]]);
    Mix(v, 3, 7, 11, 15, m[s[6]], m[s[7]]);
    Mix(v, 0, 5, 10, 15, m[s[8]], m[s[9]]);
    Mix(v, 1, 6, 11, 12, m[s[10]], m[s[11]]);
    Mix(v, 2, 7, 8, 13, m[s[12]], m[s[13]]);
    Mix(v, 3, 4, 9, 14, m[s[14]], m[s[15]]);
   }
   for (int i = 0; i < 8; i += 1)
    h[static_cast<std::size_t>(i)] ^= v[static_cast<std::size_t>(i)] ^ v[static_cast<std::size_t>(i + 8)];
  }

  // Unkeyed BLAKE2b with an 8-byte digest, returned big-endian like Python's int.from_bytes(..., "big").
  std::uint64_t Blake2b8BigEndian(const std::string &data)
  { std::array<std::uint64_t, 8> h = kIv;
   h[0] ^= 0x01010000ULL ^ 8ULL;
   std::size_t offset = 0;
   while (data.size() - offset > 128)
   { Compress(h, reinterpret_cast<const std::uint8_t *>(data.data()) + offset, offset + 128, false);
    offset += 128;
   }
   std::uint8_t block[128] = {0};
   std::size_t remaining = data.size() - offset;
   std::memcpy(block, data.data() + offset, remaining);
   Compress(h, block, data.size(), true);
   std::uint64_t result = 0;
   for (int byte_index = 0; byte_index < 8; byte_index += 1)
    result = (result << 8) | ((h[0] >> (8 * byte_index)) & 0xffULL);
   return result;
  }
 }

 std::uint64_t Simhash64(const std::string &text)
 { std::array<int, 64> weights{};
  for (const std::string &token : scoring::RelevanceTokens(text))
  { std::uint64_t token_hash = Blake2b8BigEndian(token);
   for (int bit_index = 0; bit_index < 64; bit_index += 1)
   { if ((token_hash >> bit_index) & 1ULL) weights[static_cast<std::size_t>(bit_index)] += 1;
    else weights[static_cast<std::size_t>(bit_index)] -= 1;
   }
  }
  std::uint64_t fingerprint = 0;
  for (int bit_index = 0; bit_index < 64; bit_index += 1)
   if (weights[static_cast<std::size_t>(bit_index)] > 0) fingerprint |= 1ULL << bit_index;
  return fingerprint;
 }

 int HammingDistance(std::uint64_t left, std::uint64_t right)
 { return __builtin_popcountll(left ^ right);
 }

 std::vector<EmailCandidate> CollapseNearDuplicates(const std::vector<EmailCandidate> &candidates, int max_distance)
 { std::vector<EmailCandidate> collapsed;
  if (max_distance <= 0 || candidates.size() <= 1) collapsed = candidates;
  else
  { std::vector<std::uint64_t> fingerprints;
   for (const EmailCandidate &candidate : candidates)
   { std::uint64_t fingerprint =
     Simhash64(candidate.subject() + " " + candidate.preview() + " " + candidate.body_text());
    bool is_duplicate = false;
    if (fingerprint != 0)
     for (std::uint64_t kept : fingerprints)
      if (HammingDistance(fingerprint, kept) <= max_distance) is_duplicate = true;
    if (!is_duplicate)
    { collapsed.push_back(candidate);
     if (fingerprint != 0) fingerprints.push_back(fingerprint);
    }
   }
  }
  return collapsed;
 }
}
