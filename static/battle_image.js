(function () {
  'use strict';

  const WIDTH = 2400;
  const MARGIN = 44;
  const GAP = 24;
  const PANEL_WIDTH = (WIDTH - MARGIN * 2 - GAP) / 2;
  const FONT = '"Microsoft YaHei", "Segoe UI", sans-serif';
  const COLORS = {
    background: '#101821', panel: '#1b2836', card: '#162330', line: '#34485c',
    text: '#eef4fa', muted: '#b2c4d3', blue: '#91c7f4', red: '#f2a6a5',
    gold: '#ffd17d', highlight: '#344337', highlightLine: '#e8c365',
  };

  function value(item) {
    return item === null || item === undefined || item === '' ? 'N/A' : String(item);
  }

  function rating(item) {
    const number = Number(item);
    return item === null || item === undefined || !Number.isFinite(number) ? 'N/A' : number.toFixed(1);
  }

  function country(player) {
    const countries = [...new Set((player.configured || []).map(item => item.country).filter(item => item && item !== 'N/A'))];
    return countries.length === 1 ? countries[0] : 'N/A';
  }

  function aiText(player) {
    const fields = [player.aiKills, player.aiGroundKills, player.aiNavalKills];
    if (fields.some(item => item === null || item === undefined || item === '' || !Number.isFinite(Number(item)))) return 'AI N/A';
    const counts = fields.map(Number);
    const parts = ['空中', '地面', '海上'].map((label, index) => counts[index] ? `${label} ${counts[index]}` : '').filter(Boolean);
    return `AI ${counts.reduce((sum, count) => sum + count, 0)}${parts.length ? `（${parts.join(' · ')}）` : ''}`;
  }

  function roundRect(ctx, x, y, width, height, radius, color) {
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.moveTo(x + radius, y);
    ctx.arcTo(x + width, y, x + width, y + height, radius);
    ctx.arcTo(x + width, y + height, x, y + height, radius);
    ctx.arcTo(x, y + height, x, y, radius);
    ctx.arcTo(x, y, x + width, y, radius);
    ctx.closePath();
    ctx.fill();
  }

  function wrap(ctx, text, maxWidth) {
    const lines = [];
    for (const paragraph of String(text).split('\n')) {
      let line = '';
      for (const char of paragraph) {
        if (line && ctx.measureText(line + char).width > maxWidth) {
          lines.push(line);
          line = char;
        } else {
          line += char;
        }
      }
      lines.push(line || ' ');
    }
    return lines;
  }

  function drawLines(ctx, lines, x, y, lineHeight, color) {
    ctx.fillStyle = color;
    for (const line of lines) {
      ctx.fillText(line, x, y);
      y += lineHeight;
    }
    return y;
  }

  function playerLayout(ctx, player) {
    const contentWidth = PANEL_WIDTH - 64;
    ctx.font = `700 22px ${FONT}`;
    const name = wrap(ctx, `${value(player.name)}  ·  ${country(player)}`, contentWidth - 145);
    ctx.font = `19px ${FONT}`;
    const vehicles = wrap(ctx, `载具  ${(player.configured || []).map(item => value(item.name)).join(' · ') || 'N/A'}`, contentWidth);
    ctx.font = `18px ${FONT}`;
    const stats = wrap(ctx, `空中击杀 ${value(player.kills)}   地面击杀 ${value(player.groundKills)}   死亡 ${value(player.deaths)}   助攻 ${value(player.assists)}   得分 ${value(player.score)}`, contentWidth);
    ctx.font = `17px ${FONT}`;
    const other = wrap(ctx, `UID ${value(player.uid)}   ·   ${aiText(player)}   ·   占点 ${value(player.captureZone)}   ·   击杀队友 ${value(player.teamKills)}`, contentWidth);
    const height = 20 + name.length * 29 + 7 + vehicles.length * 25 + 7 + stats.length * 24 + 5 + other.length * 23 + 17;
    return { player, name, vehicles, stats, other, height };
  }

  function teamLayout(ctx, team, players) {
    const sorted = players.map((player, index) => ({ player, index })).sort((a, b) => {
      const aBr = Number(a.player.max_br), bBr = Number(b.player.max_br);
      const aMissing = a.player.max_br === null || a.player.max_br === undefined || !Number.isFinite(aBr);
      const bMissing = b.player.max_br === null || b.player.max_br === undefined || !Number.isFinite(bBr);
      return aMissing !== bMissing ? (aMissing ? 1 : -1) : aMissing ? a.index - b.index : bBr - aBr || a.index - b.index;
    }).map(item => item.player);
    const rows = sorted.map(player => playerLayout(ctx, player));
    return { team, rows, height: 70 + (rows.length ? rows.reduce((sum, row) => sum + row.height + 8, 0) : 66) + 12 };
  }

  function drawTeam(ctx, layout, x, y, highlightUid) {
    const blue = String(layout.team) === '1';
    const red = String(layout.team) === '2';
    const accent = blue ? COLORS.blue : red ? COLORS.red : COLORS.muted;
    const title = blue ? '蓝队' : red ? '红队' : `队伍 ${value(layout.team)}`;
    roundRect(ctx, x, y, PANEL_WIDTH, layout.height, 15, COLORS.panel);
    roundRect(ctx, x + 12, y + 12, PANEL_WIDTH - 24, 48, 8, blue ? '#203d54' : red ? '#4a3039' : '#344456');
    ctx.font = `700 25px ${FONT}`;
    ctx.fillStyle = accent;
    ctx.fillText(`${title} · ${layout.rows.length} 人`, x + 30, y + 44);
    let rowY = y + 70;
    if (!layout.rows.length) {
      ctx.font = `20px ${FONT}`;
      ctx.fillStyle = COLORS.muted;
      ctx.fillText('暂无玩家结算数据', x + 30, rowY + 35);
    }
    for (const row of layout.rows) {
      const selected = highlightUid !== null && String(row.player.uid) === highlightUid;
      roundRect(ctx, x + 14, rowY, PANEL_WIDTH - 28, row.height, 9, selected ? COLORS.highlight : COLORS.card);
      if (selected) roundRect(ctx, x + 14, rowY, 5, row.height, 2, COLORS.highlightLine);
      const left = x + 32;
      let textY = rowY + 29;
      ctx.font = `700 22px ${FONT}`;
      textY = drawLines(ctx, row.name, left, textY, 29, selected ? COLORS.gold : COLORS.text);
      ctx.font = `700 22px ${FONT}`;
      ctx.fillStyle = selected ? COLORS.gold : accent;
      ctx.textAlign = 'right';
      ctx.fillText(`BR ${rating(row.player.max_br)}`, x + PANEL_WIDTH - 32, rowY + 29);
      ctx.textAlign = 'left';
      textY += 7;
      ctx.font = `19px ${FONT}`;
      textY = drawLines(ctx, row.vehicles, left, textY, 25, COLORS.text);
      textY += 7;
      ctx.font = `18px ${FONT}`;
      textY = drawLines(ctx, row.stats, left, textY, 24, COLORS.text);
      textY += 5;
      ctx.font = `17px ${FONT}`;
      drawLines(ctx, row.other, left, textY, 23, COLORS.muted);
      rowY += row.height + 8;
    }
  }

  function metaLayout(ctx, label, text) {
    ctx.font = `22px ${FONT}`;
    const lines = wrap(ctx, text, (WIDTH - 2 * MARGIN - 2 * GAP) / 3 - 38);
    return { label, lines };
  }

  function render(data, highlightUid = null) {
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    if (!ctx) throw new Error('浏览器无法创建图片画布。');
    const groups = new Map([[1, []], [2, []]]);
    for (const player of data.players || []) {
      const team = Number(player.team);
      if (!groups.has(team)) groups.set(team, []);
      groups.get(team).push(player);
    }
    const teams = [...groups].map(([team, players]) => teamLayout(ctx, team, players));
    const groupLabels = { aircraft: '空战', aviation: '空战', air: '空战', tank: '陆战', ground: '陆战', ship: '海战' };
    const modeLabels = { arcade: '街机', realistic: '历史', simulation: '全真' };
    const metadata = [
      metaLayout(ctx, '开始时间 (UTC)', value(data.start_utc)),
      metaLayout(ctx, '地图', value(data.map || data.level)),
      metaLayout(ctx, 'Session ID', value(data.sid)),
      metaLayout(ctx, '对局模式', `${value(groupLabels[data.battle_group] || data.battle_group)} · ${value(modeLabels[data.game_mode] || data.game_mode)}`),
      metaLayout(ctx, '对局权重', rating(data.match_br)),
      metaLayout(ctx, '数据来源', `${value(data.source)} · ${value(data.parts)} 段`),
    ];
    const metaHeight = [0, 3].map(start => Math.max(...metadata.slice(start, start + 3).map(item => 40 + item.lines.length * 29)) + 12);
    const teamsTop = 104 + metaHeight[0] + metaHeight[1] + 62;
    const teamRows = [];
    let totalTeamHeight = 0;
    for (let index = 0; index < teams.length; index += 2) {
      const height = Math.max(...teams.slice(index, index + 2).map(item => item.height));
      teamRows.push({ index, y: teamsTop + totalTeamHeight });
      totalTeamHeight += height + GAP;
    }
    canvas.width = WIDTH;
    canvas.height = teamsTop + totalTeamHeight + 18;
    ctx.fillStyle = COLORS.background;
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.font = `700 34px ${FONT}`;
    ctx.fillStyle = COLORS.text;
    ctx.fillText('WTStat · 对局详情', MARGIN, 65);
    ctx.font = `18px ${FONT}`;
    ctx.fillStyle = COLORS.muted;
    ctx.textAlign = 'right';
    ctx.fillText('最终战绩 · 队内按权重从高到低', WIDTH - MARGIN, 60);
    ctx.textAlign = 'left';
    const metaWidth = (WIDTH - 2 * MARGIN - 2 * GAP) / 3;
    let metaY = 104;
    for (let row = 0; row < 2; row++) {
      const height = metaHeight[row] - 12;
      for (let column = 0; column < 3; column++) {
        const item = metadata[row * 3 + column];
        const x = MARGIN + column * (metaWidth + GAP);
        roundRect(ctx, x, metaY, metaWidth, height, 9, COLORS.card);
        ctx.font = `16px ${FONT}`;
        ctx.fillStyle = COLORS.muted;
        ctx.fillText(item.label, x + 18, metaY + 26);
        ctx.font = `22px ${FONT}`;
        drawLines(ctx, item.lines, x + 18, metaY + 58, 29, COLORS.text);
      }
      metaY += metaHeight[row];
    }
    ctx.font = `17px ${FONT}`;
    ctx.fillStyle = COLORS.muted;
    ctx.fillText(`官网对局页  https://warthunder.com/en/tournament/replay/${BigInt(`0x${data.sid}`)}`, MARGIN, metaY + 25);
    for (const row of teamRows) {
      drawTeam(ctx, teams[row.index], MARGIN, row.y, highlightUid);
      if (teams[row.index + 1]) drawTeam(ctx, teams[row.index + 1], MARGIN + PANEL_WIDTH + GAP, row.y, highlightUid);
    }
    return canvas;
  }

  window.WTStatBattleImage = { render };
})();
