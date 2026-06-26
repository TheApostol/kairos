type PolkorpBrandMarkProps = {
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

const markSizes = {
  sm: 'h-12 w-12 rounded-xl text-2xl',
  md: 'h-16 w-16 rounded-2xl text-3xl',
  lg: 'h-20 w-20 rounded-[20px] text-4xl',
}

export function PolkorpBrandMark({ size = 'md', className = '' }: PolkorpBrandMarkProps) {
  return (
    <div
      aria-label="Polkorp"
      className={`relative flex shrink-0 items-center justify-center overflow-hidden border border-white/15 bg-[#050914] shadow-[0_20px_50px_rgba(11,95,255,0.25)] ${markSizes[size]} ${className}`}
    >
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_30%_25%,rgba(47,168,255,0.32),transparent_34%),linear-gradient(135deg,rgba(255,255,255,0.12),rgba(11,95,255,0.18))]" />
      <span className="relative translate-x-1 font-black tracking-normal text-[#C9CED6]">P</span>
      <b className="relative -translate-x-1 font-black tracking-normal text-[#2FA8FF]">K</b>
    </div>
  )
}

type PolkorpWordmarkProps = {
  compact?: boolean
}

export function PolkorpWordmark({ compact = false }: PolkorpWordmarkProps) {
  return (
    <div className={compact ? 'leading-tight' : 'leading-tight'}>
      <div className="text-sm font-black uppercase tracking-[0.32em] text-[#F5F7FA]">Polkorp</div>
      {!compact && (
        <div className="mt-1 text-xs font-medium uppercase tracking-[0.2em] text-[#9BA6B6]">
          AI Systems & Strategic Advisory
        </div>
      )}
    </div>
  )
}
