<script>
  import { Styles as BootstrapStyles } from '@sveltestrap/sveltestrap';

  let { children } = $props();
</script>

<BootstrapStyles />

{@render children()}
