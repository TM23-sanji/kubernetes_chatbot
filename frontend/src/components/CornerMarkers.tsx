interface CornerMarkersProps {
  large?: boolean;
}

export function CornerMarkers({ large }: CornerMarkersProps) {
  const s = large ? "w-3 h-3" : "w-2 h-2";
  return (
    <>
      <span className={`absolute -top-[1px] -left-[1px] ${s} border-l border-t border-black/60`} />
      <span className={`absolute -top-[1px] -right-[1px] ${s} border-r border-t border-black/60`} />
      <span className={`absolute -bottom-[1px] -left-[1px] ${s} border-l border-b border-black/60`} />
      <span className={`absolute -bottom-[1px] -right-[1px] ${s} border-r border-b border-black/60`} />
    </>
  );
}
