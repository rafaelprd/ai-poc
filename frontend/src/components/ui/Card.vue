<script setup lang="ts">
defineOptions({
  inheritAttrs: false,
})

const props = withDefaults(
  defineProps<{
    as?: string
    className?: string
  }>(),
  {
    as: 'div',
    className: '',
  },
)
</script>

<template>
  <component :is="props.as" class="panel" :class="props.className" v-bind="$attrs">
    <slot />
  </component>
</template>
