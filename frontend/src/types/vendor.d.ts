declare module 'wordcloud' {
  export interface WordCloudOptions {
    list: Array<[string, number, unknown?]>
    gridSize?: number
    weightFactor?: number | ((size: number) => number)
    fontFamily?: string
    fontWeight?: string
    color?: string | ((word: string, weight: number, fontSize: number, distance: number, theta: number, extraData?: unknown) => string)
    backgroundColor?: string
    rotateRatio?: number
    rotationSteps?: number
    minRotation?: number
    maxRotation?: number
    shape?: string
    ellipticity?: number
    hover?: (item: [string, number, unknown?] | undefined, dimension: unknown, event: MouseEvent) => void
    click?: (item: [string, number, unknown?] | undefined, dimension: unknown, event: MouseEvent) => void
  }

  export interface WordCloud {
    (element: HTMLCanvasElement | HTMLElement, options: WordCloudOptions): void
    isSupported?: boolean
    stop?: () => void
  }

  const WordCloud: WordCloud
  export default WordCloud
}

declare module 'stopwords-zh' {
  const words: string[]
  export default words
}
