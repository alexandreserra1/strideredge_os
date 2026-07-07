// Moldura de navegador p/ prints reais do produto (landing e login).
// O print É o marketing: mais autêntico que foto de banco de imagem.
export default function AppFrame({ src, alt, className = '' }: {
  src: string; alt: string; className?: string
}) {
  return (
    <div className={`rounded-2xl border border-border-light bg-surface-100 shadow-2xl overflow-hidden ${className}`}>
      <div className="flex items-center gap-1.5 px-4 py-2.5 border-b border-border-light bg-surface-200">
        <span className="w-2.5 h-2.5 rounded-full bg-[#FB5E7E]" />
        <span className="w-2.5 h-2.5 rounded-full bg-[#FBBF24]" />
        <span className="w-2.5 h-2.5 rounded-full bg-[#34D399]" />
      </div>
      <img src={src} alt={alt} className="block w-full" loading="lazy" />
    </div>
  )
}
