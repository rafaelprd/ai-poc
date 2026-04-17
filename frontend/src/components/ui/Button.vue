<script setup lang="ts">
import { computed, useAttrs } from 'vue'

defineOptions({
  inheritAttrs: false,
})

type ButtonVariant =
  | 'default'
  | 'secondary'
  | 'destructive'
  | 'outline'
  | 'ghost'
  | 'link'

type ButtonSize = 'default' | 'sm' | 'lg' | 'icon'

const props = withDefaults(
  defineProps<{
    variant?: ButtonVariant
    size?: ButtonSize
    type?: 'button' | 'submit' | 'reset'
    disabled?: boolean
  }>(),
  {
    variant: 'default',
    size: 'default',
    type: 'button',
    disabled: false,
  },
)

const attrs = useAttrs()

const variantClasses: Record<ButtonVariant, string> = {
  default: 'buttonPrimary',
  secondary: 'buttonSecondary',
  destructive: 'buttonDanger',
  outline: 'buttonGhost',
  ghost: 'buttonGhost',
  link: 'buttonLink',
}

const sizeClasses: Record<ButtonSize, string> = {
  default: '',
  sm: 'buttonCompact',
  lg: 'buttonLarge',
  icon: 'buttonIconOnly',
}

const buttonClass = computed(() => [
  'button',
  variantClasses[props.variant],
  sizeClasses[props.size],
].join(' '))
</script>

<template>
  <button
    v-bind="attrs"
    :type="props.type"
    :disabled="props.disabled"
    :class="buttonClass"
  >
    <slot />
  </button>
</template>
