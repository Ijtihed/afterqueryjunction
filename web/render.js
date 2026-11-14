// Shared canvas renderer. It draws exactly the symbol grids produced by the
// simulator; it holds no game state of its own.
(function () {
  const WALL = '#', EMPTY = '.';
  const hash = (x, y) => { let h = (x * 374761393 + y * 668265263) >>> 0; h = ((h ^ (h >>> 13)) * 1274126177) >>> 0; return ((h ^ (h >>> 16)) >>> 0) / 4294967295; };
  const hex = (c) => { const n = parseInt(c.slice(1), 16); return [(n >> 16) & 255, (n >> 8) & 255, n & 255]; };
  const shade = (c, k) => { const [r, g, b] = hex(c); const f = (v) => Math.max(0, Math.min(255, Math.round(v * k))); return `rgb(${f(r)},${f(g)},${f(b)})`; };

  class Stage {
    constructor(canvas, opts = {}) {
      this.canvas = canvas; this.ctx = canvas.getContext('2d');
      this.glow = document.createElement('canvas'); this.gctx = this.glow.getContext('2d');
      this.legend = opts.legend || {}; this.maxCell = opts.maxCell || 30;
      this.zones = []; this.rows = null; this.selGate = null; this.flash = 0; this.dim = false;
      this.onCell = null; this._timer = null; this.t0 = performance.now();
      canvas.addEventListener('pointerdown', (e) => this._pointer(e, true));
      canvas.addEventListener('pointermove', (e) => { if (e.buttons) this._pointer(e, false); });
    }
    _pointer(e, down) {
      if (!this.onCell || !this.rows) return;
      const r = this.canvas.getBoundingClientRect();
      const x = Math.floor((e.clientX - r.left) / r.width * this.w), y = Math.floor((e.clientY - r.top) / r.height * this.h);
      if (x >= 0 && y >= 0 && x < this.w && y < this.h) this.onCell(x, y, down);
    }
    setLegend(l) { this.legend = Object.assign({}, this.legend, l); }
    fit(w, h) {
      const avail = this.canvas.parentElement ? this.canvas.parentElement.clientWidth - 2 : 600;
      const cell = Math.max(8, Math.min(this.maxCell, Math.floor(avail / w)));
      const dpr = window.devicePixelRatio || 1;
      if (this.w === w && this.h === h && this.cell === cell) return;
      this.w = w; this.h = h; this.cell = cell;
      for (const c of [this.canvas, this.glow]) { c.width = w * cell * dpr; c.height = h * cell * dpr; }
      this.canvas.style.width = w * cell + 'px'; this.canvas.style.height = h * cell + 'px';
      this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0); this.gctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
    draw(rows) {
      if (rows) this.rows = rows; rows = this.rows; if (!rows) return;
      const h = rows.length, w = rows[0].length; this.fit(w, h);
      const s = this.cell, ctx = this.ctx, g = this.gctx, now = (performance.now() - this.t0) / 1000;
      ctx.fillStyle = '#050506'; ctx.fillRect(0, 0, w * s, h * s);
      g.clearRect(0, 0, w * s, h * s);
      for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
        const c = rows[y][x], px = x * s, py = y * s, n = hash(x, y);
        if (c === EMPTY) { if (n > 0.93) { ctx.fillStyle = 'rgba(120,150,190,0.05)'; ctx.fillRect(px + s * .45, py + s * .45, 1.5, 1.5); } continue; }
        if (c === WALL) {
          ctx.fillStyle = shade('#2c2c2e', 0.9 + n * 0.16); ctx.fillRect(px, py, s, s);
          ctx.fillStyle = 'rgba(255,255,255,0.045)'; ctx.fillRect(px, py, s, 1);
          ctx.fillStyle = 'rgba(0,0,0,0.35)'; ctx.fillRect(px, py + s - 1, s, 1);
          continue;
        }
        if (c >= '0' && c <= '9') {
          const sel = this.selGate === +c, pulse = sel ? 0.75 + 0.25 * Math.sin(now * 7) : 0.55;
          ctx.fillStyle = `rgba(10,132,255,${0.3 * pulse + (sel ? 0.35 : 0.1)})`; ctx.fillRect(px, py, s, s);
          ctx.strokeStyle = `rgba(100,180,255,${pulse})`; ctx.lineWidth = sel ? 2 : 1; ctx.strokeRect(px + 1.5, py + 1.5, s - 3, s - 3);
          ctx.fillStyle = '#ffffff'; ctx.font = `600 ${Math.max(8, s * 0.56)}px ui-monospace, 'SF Mono', Menlo, Consolas, monospace`;
          ctx.textAlign = 'center'; ctx.textBaseline = 'middle'; ctx.fillText(c, px + s / 2, py + s / 2 + 0.5);
          if (sel) { g.fillStyle = 'rgba(10,132,255,0.9)'; g.fillRect(px, py, s, s); }
          continue;
        }
        const col = (this.legend[c] && this.legend[c].color) || '#9aa4b2';
        ctx.fillStyle = shade(col, 0.9 + n * 0.14); ctx.beginPath(); ctx.roundRect(px + 0.75, py + 0.75, s - 1.5, s - 1.5, s * 0.22); ctx.fill();
        g.fillStyle = col; g.fillRect(px, py, s, s);
      }
      ctx.save(); ctx.globalCompositeOperation = 'lighter'; ctx.globalAlpha = 0.26; ctx.filter = `blur(${Math.max(3, s * 0.45)}px)`;
      ctx.drawImage(this.glow, 0, 0, w * s, h * s); ctx.restore();
      for (const z of this.zones) {
        const x0 = z.x[0] * s, y0 = z.y[0] * s, zw = (z.x[1] - z.x[0] + 1) * s, zh = (z.y[1] - z.y[0] + 1) * s;
        const col = z.met ? '#30d158' : ((this.legend[z.substance] || {}).color || '#8fd3ff');
        ctx.save(); ctx.setLineDash([5, 4]); ctx.lineDashOffset = -now * 6; ctx.strokeStyle = col; ctx.lineWidth = 1.5; ctx.globalAlpha = 0.9;
        ctx.strokeRect(x0 + 1, y0 + 1, zw - 2, zh - 2); ctx.setLineDash([]);
        const label = `${z.zone}  ${z.current_cells}/${z.min_cells}${z.met ? '  ✓' : ''}`;
        ctx.font = `600 ${Math.max(9, Math.min(12, s * 0.5))}px ui-monospace, 'SF Mono', Menlo, Consolas, monospace`;
        const tw = ctx.measureText(label).width + 8; ctx.fillStyle = 'rgba(7,9,13,0.85)'; ctx.fillRect(x0 + 2, y0 + 2, tw, 15);
        ctx.fillStyle = col; ctx.textAlign = 'left'; ctx.textBaseline = 'top'; ctx.fillText(label, x0 + 6, y0 + 4); ctx.restore();
      }
      if (this.flash > 0) { ctx.fillStyle = `rgba(255,60,60,${this.flash * 0.35})`; ctx.fillRect(0, 0, w * s, h * s); }
      if (this.dim) { ctx.fillStyle = 'rgba(7,9,13,0.5)'; ctx.fillRect(0, 0, w * s, h * s); }
    }
    stop() { if (this._timer) { cancelAnimationFrame(this._timer); this._timer = null; } }
    // Plays frames at `tps` simulator ticks per second, then resolves.
    play(frames, tps = 40, onFrame) {
      this.stop();
      return new Promise((resolve) => {
        if (!frames || !frames.length) return resolve();
        const start = performance.now(); let last = -1;
        const tick = () => {
          const i = Math.min(frames.length - 1, Math.floor((performance.now() - start) / 1000 * tps));
          if (i !== last) { last = i; this.draw(frames[i]); if (onFrame) onFrame(i, frames.length); } else this.draw();
          if (i >= frames.length - 1) { this._timer = null; return resolve(); }
          this._timer = requestAnimationFrame(tick);
        };
        tick();
      });
    }
    // Keeps animated overlays (zone outlines, selected gate) alive while idle.
    idle() { const loop = () => { if (!this._timer && this.rows) this.draw(); this._idle = requestAnimationFrame(loop); }; if (!this._idle) loop(); }
  }
  window.CrucibleStage = Stage;
})();
