/* Deterministic cellular matter simulation. Integer state only, fixed scan
 * order, no randomness: the same inputs always give the same outputs. */
#include <stdint.h>
#include <string.h>

#define EMPTY 0
#define WALL 1
#define MAT0 8 /* ids below this are structural (wall, gate) and never move */
#define NID 32
#define MAXN 8192
#define NO_RX 255

#define SOLID 0
#define POWDER 1
#define LIQUID 2

typedef struct {
    int w, h, tick;
    uint8_t *cell, *aux; /* aux: bit0 = prefers right */
    const int8_t *phase, *grav;
    const int16_t *dens;
    const uint8_t *rx, *rxneed;
    uint32_t *rxcount;
    uint8_t moved[MAXN];
} Sim;

static int is_liquid(const Sim *s, int t) { return t >= MAT0 && s->phase[t] == LIQUID; }

/* Can c displace t while travelling along its own gravity? */
static int passable(const Sim *s, int c, int j) {
    int t = s->cell[j];
    if (t == EMPTY) return 1;
    if (!is_liquid(s, t) || s->moved[j]) return 0;
    if (s->grav[t] != s->grav[c]) return 1;
    return s->dens[c] > s->dens[t];
}

static int side_passable(const Sim *s, int c, int j) {
    int t = s->cell[j];
    if (t == EMPTY) return 1;
    if (!is_liquid(s, t) || s->moved[j]) return 0;
    return s->grav[t] == s->grav[c] && s->dens[c] > s->dens[t];
}

static void swap_cells(Sim *s, int i, int j, uint8_t new_aux) {
    uint8_t c = s->cell[i], t = s->cell[j], ta = s->aux[j];
    s->cell[j] = c; s->aux[j] = new_aux; s->moved[j] = 1;
    s->cell[i] = t; s->aux[i] = ta;
    if (t != EMPTY) s->moved[i] = 1;
}

static int try_cell(Sim *s, int x, int y) {
    int w = s->w, h = s->h, i = y * w + x;
    int c = s->cell[i];
    if (c < MAT0 || s->moved[i]) return 0;
    int ph = s->phase[c];
    if (ph == SOLID) return 0;
    int g = s->grav[c], ny = y + g;
    uint8_t a = s->aux[i];
    int d = (a & 1) ? 1 : -1;

    if (ny >= 0 && ny < h) {
        int j = ny * w + x;
        if (passable(s, c, j)) { swap_cells(s, i, j, a & 1); return 1; }
        for (int k = 0; k < 2; k++) {
            int dx = k == 0 ? d : -d, nx = x + dx;
            if (nx < 0 || nx >= w) continue;
            int side = s->cell[y * w + nx];
            if (side != EMPTY && !is_liquid(s, side)) continue;
            int jj = ny * w + nx;
            if (passable(s, c, jj)) { swap_cells(s, i, jj, dx > 0 ? 1 : 0); return 1; }
        }
    }
    if (ph != LIQUID) return 0;

    /* A liquid creeps sideways only toward the nearest spot where it can
     * keep travelling along its gravity, so pools drain and then rest. */
    int best = 0, bestdx = 0;
    for (int k = 0; k < 2; k++) {
        int dx = k == 0 ? d : -d;
        for (int n = 1; n < w; n++) {
            int nx = x + dx * n;
            if (nx < 0 || nx >= w) break;
            int j = y * w + nx;
            if (!side_passable(s, c, j)) break;
            if (ny >= 0 && ny < h && passable(s, c, ny * w + nx)) {
                if (best == 0 || n < best) { best = n; bestdx = dx; }
                break;
            }
        }
    }
    if (best) { swap_cells(s, i, y * w + x + bestdx, bestdx > 0 ? 1 : 0); return 1; }

    /* Pressure: a liquid run with liquid stacked on any part of it pushes its
     * end cell into an adjacent gap, so a body levels out along a floor. */
    int py = y - g;
    if (py < 0 || py >= h) return 0;
    for (int k = 0; k < 2; k++) {
        int dx = k == 0 ? d : -d, nx = x + dx;
        if (nx < 0 || nx >= w || s->cell[y * w + nx] != EMPTY) continue;
        for (int bx = x; bx >= 0 && bx < w; bx -= dx) {
            int t = s->cell[y * w + bx];
            if (!is_liquid(s, t) || s->grav[t] != g) break;
            int up = s->cell[py * w + bx];
            if (is_liquid(s, up) && s->grav[up] == g) {
                swap_cells(s, i, y * w + nx, dx > 0 ? 1 : 0);
                return 1;
            }
        }
    }
    return 0;
}

/* Some reactions need bulk: a cell reacts only with enough of its own kind beside it. */
static int same_neighbours(const Sim *s, int x, int y, int a) {
    int n = 0;
    if (x > 0 && s->cell[y * s->w + x - 1] == a) n++;
    if (x < s->w - 1 && s->cell[y * s->w + x + 1] == a) n++;
    if (y > 0 && s->cell[(y - 1) * s->w + x] == a) n++;
    if (y < s->h - 1 && s->cell[(y + 1) * s->w + x] == a) n++;
    return n;
}

static int react(Sim *s) {
    static const int DX[4] = {0, 1, 0, -1}, DY[4] = {-1, 0, 1, 0};
    int w = s->w, h = s->h, n = 0;
    memset(s->moved, 0, (size_t)(w * h));
    for (int y = 0; y < h; y++) for (int x = 0; x < w; x++) {
        int i = y * w + x, a = s->cell[i];
        if (a < MAT0 || s->moved[i]) continue;
        for (int k = 0; k < 4; k++) {
            int xx = x + DX[k], yy = y + DY[k];
            if (xx < 0 || xx >= w || yy < 0 || yy >= h) continue;
            int j = yy * w + xx, b = s->cell[j];
            if ((b < MAT0 && b != WALL) || s->moved[j]) continue;
            const uint8_t *r = &s->rx[(a * NID + b) * 2];
            if (r[0] == NO_RX) continue;
            if (same_neighbours(s, x, y, a) < s->rxneed[a * NID + b]) continue;
            if (b != WALL && same_neighbours(s, xx, yy, b) < s->rxneed[b * NID + a]) continue;
            s->cell[i] = r[0]; s->cell[j] = r[1];
            s->aux[i] = (uint8_t)((x + y + s->tick) & 1);
            s->aux[j] = (uint8_t)((xx + yy + s->tick) & 1);
            s->moved[i] = s->moved[j] = 1;
            if (s->rxcount) s->rxcount[a * NID + b]++;
            n++;
            break;
        }
    }
    return n;
}

static int step(Sim *s) {
    int w = s->w, h = s->h, n = 0;
    int ltr = (s->tick & 1) == 0;
    memset(s->moved, 0, (size_t)(w * h));
    for (int y = h - 1; y >= 0; y--)
        for (int k = 0; k < w; k++) {
            int x = ltr ? k : w - 1 - k, c = s->cell[y * w + x];
            if (c >= MAT0 && s->grav[c] > 0) n += try_cell(s, x, y);
        }
    for (int y = 0; y < h; y++)
        for (int k = 0; k < w; k++) {
            int x = ltr ? k : w - 1 - k, c = s->cell[y * w + x];
            if (c >= MAT0 && s->grav[c] < 0) n += try_cell(s, x, y);
        }
    n += react(s);
    s->tick++;
    return n;
}

/* Runs until a tick changes nothing or max_ticks elapse. Returns ticks that
 * changed something; *settled is 1 when a fixed point was reached. */
int cr_settle(int w, int h, uint8_t *cell, uint8_t *aux,
              const int8_t *phase, const int8_t *grav, const int16_t *dens,
              const uint8_t *rx, const uint8_t *rxneed, int tick0, int max_ticks,
              uint8_t *frames, int max_frames, int *nframes,
              uint32_t *rxcount, int *settled) {
    static Sim s;
    if (w <= 0 || h <= 0 || w * h > MAXN) return -1;
    s.w = w; s.h = h; s.tick = tick0; s.cell = cell; s.aux = aux;
    s.phase = phase; s.grav = grav; s.dens = dens; s.rx = rx; s.rxneed = rxneed; s.rxcount = rxcount;
    int t = 0, nf = 0;
    *settled = 0;
    while (t < max_ticks) {
        if (step(&s) == 0) { *settled = 1; break; }
        t++;
        if (frames && nf < max_frames) {
            memcpy(frames + (size_t)nf * (size_t)(w * h), cell, (size_t)(w * h));
            nf++;
        }
    }
    if (nframes) *nframes = nf;
    return t;
}
