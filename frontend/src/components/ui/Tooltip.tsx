import {
  cloneElement,
  isValidElement,
  ReactElement,
  ReactNode,
  Ref,
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react'
import { createPortal } from 'react-dom'

type TooltipPosition = {
  left: number
  top: number
}

function mergeRefs<T>(...refs: Array<Ref<T> | undefined>) {
  return (value: T | null) => {
    refs.forEach((ref) => {
      if (!ref) {
        return
      }
      if (typeof ref === 'function') {
        ref(value)
        return
      }
      ;(ref as { current: T | null }).current = value
    })
  }
}

function callHandler<EventType>(
  handler: ((event: EventType) => void) | undefined,
  event: EventType
) {
  handler?.(event)
}

interface TooltipProps {
  content?: ReactNode | null
  children: ReactElement
  delayMs?: number
}

export default function Tooltip({ content, children, delayMs = 350 }: TooltipProps) {
  const anchorRef = useRef<HTMLElement | null>(null)
  const tooltipRef = useRef<HTMLDivElement | null>(null)
  const showTimerRef = useRef<number | null>(null)
  const pointerFocusRef = useRef(false)
  const pointerPositionRef = useRef<{ x: number; y: number } | null>(null)
  const [visible, setVisible] = useState(false)
  const [position, setPosition] = useState<TooltipPosition>({ left: -9999, top: -9999 })

  const clearTimer = useCallback(() => {
    if (showTimerRef.current !== null) {
      window.clearTimeout(showTimerRef.current)
      showTimerRef.current = null
    }
  }, [])

  const updatePosition = useCallback(() => {
    const anchor = anchorRef.current
    const tooltip = tooltipRef.current
    if (!anchor || !tooltip) {
      return
    }

    const anchorRect = anchor.getBoundingClientRect()
    const tooltipRect = tooltip.getBoundingClientRect()
    const pointer = pointerPositionRef.current
    const viewportWidth = window.innerWidth
    const viewportHeight = window.innerHeight
    const edgePadding = 8
    const cursorGap = 14
    const anchorGap = 10

    const baseX = pointer?.x ?? anchorRect.left + anchorRect.width / 2
    const baseY = pointer?.y ?? anchorRect.top

    let left = pointer ? baseX + cursorGap : baseX - tooltipRect.width / 2
    if (left + tooltipRect.width > viewportWidth - edgePadding) {
      left = pointer ? baseX - tooltipRect.width - cursorGap : viewportWidth - tooltipRect.width - edgePadding
    }
    left = Math.min(Math.max(left, edgePadding), viewportWidth - tooltipRect.width - edgePadding)

    const topAbovePointer = baseY - tooltipRect.height - cursorGap
    const topAboveAnchor = anchorRect.top - tooltipRect.height - anchorGap
    const preferredTop = pointer ? topAbovePointer : topAboveAnchor

    let top = preferredTop
    if (top < edgePadding) {
      const belowPointer = (pointer?.y ?? anchorRect.bottom) + cursorGap
      const belowAnchor = anchorRect.bottom + anchorGap
      top = pointer ? belowPointer : belowAnchor
    }
    top = Math.min(Math.max(top, edgePadding), viewportHeight - tooltipRect.height - edgePadding)

    setPosition({ left, top })
  }, [])

  const hide = useCallback(() => {
    clearTimer()
    setVisible(false)
  }, [clearTimer])

  const scheduleShow = useCallback(() => {
    if (!content) {
      return
    }
    clearTimer()
    showTimerRef.current = window.setTimeout(() => {
      setVisible(true)
      showTimerRef.current = null
    }, delayMs)
  }, [clearTimer, content, delayMs])

  useEffect(() => {
    return () => {
      clearTimer()
    }
  }, [clearTimer])

  useEffect(() => {
    if (!visible) {
      return
    }

    updatePosition()
    const handleViewportChange = () => updatePosition()
    window.addEventListener('resize', handleViewportChange)
    window.addEventListener('scroll', handleViewportChange, true)
    return () => {
      window.removeEventListener('resize', handleViewportChange)
      window.removeEventListener('scroll', handleViewportChange, true)
    }
  }, [updatePosition, visible])

  if (!content || !isValidElement(children)) {
    return children
  }

  const child = children as ReactElement<any> & { ref?: Ref<HTMLElement> }
  const mergedRef = mergeRefs<HTMLElement>(
    (node) => {
      anchorRef.current = node
    },
    child.ref
  )

  const enhancedChild = cloneElement<any>(child, {
    ref: mergedRef,
    onMouseEnter: (event: React.MouseEvent<HTMLElement>) => {
      pointerPositionRef.current = { x: event.clientX, y: event.clientY }
      scheduleShow()
      callHandler((children.props as any).onMouseEnter, event)
    },
    onMouseMove: (event: React.MouseEvent<HTMLElement>) => {
      pointerPositionRef.current = { x: event.clientX, y: event.clientY }
      if (visible) {
        updatePosition()
      }
      callHandler((children.props as any).onMouseMove, event)
    },
    onMouseLeave: (event: React.MouseEvent<HTMLElement>) => {
      hide()
      callHandler((children.props as any).onMouseLeave, event)
    },
    onFocus: (event: React.FocusEvent<HTMLElement>) => {
      if (pointerFocusRef.current) {
        pointerFocusRef.current = false
      } else {
        pointerPositionRef.current = null
        scheduleShow()
      }
      callHandler((children.props as any).onFocus, event)
    },
    onBlur: (event: React.FocusEvent<HTMLElement>) => {
      hide()
      callHandler((children.props as any).onBlur, event)
    },
    onMouseDown: (event: React.MouseEvent<HTMLElement>) => {
      pointerFocusRef.current = true
      hide()
      callHandler((children.props as any).onMouseDown, event)
    },
    onKeyDown: (event: React.KeyboardEvent<HTMLElement>) => {
      if (event.key === 'Escape') {
        hide()
      }
      callHandler((children.props as any).onKeyDown, event)
    },
  })

  return (
    <>
      {enhancedChild}
      {visible
        ? createPortal(
            <div
              ref={tooltipRef}
              role="tooltip"
              className="pointer-events-none fixed z-[400] max-w-56 rounded-md bg-slate-900 px-2 py-1 text-[11px] font-medium text-white shadow-lg"
              style={{ left: position.left, top: position.top }}
            >
              {content}
            </div>,
            document.body
          )
        : null}
    </>
  )
}
