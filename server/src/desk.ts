/**
 * Map desk IDs like "A2" or "A2-1" to classroom coordinates (meters).
 * Desk centers sit on a 2 m grid; seats at the same desk are 1 m apart.
 */
export function deskIdToCoords(deskId: string): { x: number; y: number } {
  const match = deskId.trim().toUpperCase().match(/^([A-Z]+)(\d+)(?:-(\d+))?$/);
  if (!match) {
    throw new Error(`Invalid desk id: ${deskId}`);
  }

  const colLetters = match[1];
  const row = Number(match[2]);
  const seatIndex = match[3] ? Number(match[3]) - 1 : 0;

  let col = 0;
  for (let i = 0; i < colLetters.length; i++) {
    col = col * 26 + (colLetters.charCodeAt(i) - 64);
  }
  col -= 1;

  const deskX = col * 2;
  const deskY = (row - 1) * 2;

  // Spread multiple seats around the desk center (±0.5 m horizontally)
  const seatOffsetX = (seatIndex % 2 === 0 ? -0.5 : 0.5) * (seatIndex > 0 || match[3] ? 1 : 0);
  const seatOffsetY = Math.floor(seatIndex / 2) * 1.0;

  return {
    x: deskX + seatOffsetX,
    y: deskY + seatOffsetY,
  };
}

export function isValidDeskId(deskId: string): boolean {
  return /^[A-Za-z]+\d+(-\d+)?$/.test(deskId.trim());
}
