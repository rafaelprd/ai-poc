<script setup lang="ts">
import { computed } from 'vue'

type BadgeVariant = 'default' | 'secondary' | 'success' | 'warning' | 'destructive'

const props = withDefaults(
  defineProps<{
    variant?: BadgeVariant
  }>(),
  {
    variant: 'default',
  },
)

const variantClasses: Record<BadgeVariant, string> = {
  default: 'badge',
  secondary: 'badge',
  success: 'badge pillSuccess',
  warning: 'badge pillWarning',
  destructive: 'badge pillDanger',
}

const badgeClass = computed(() => variantClasses[props.variant])
</script>

<template>
  <span :class="badgeClass">
    <slot />
  </span>
</template>
