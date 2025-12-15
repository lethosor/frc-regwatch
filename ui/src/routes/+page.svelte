<script>
  import { onMount } from 'svelte';
  import { Container, Spinner } from '@sveltestrap/sveltestrap';

  onMount(() => {
    const queryStr = location.search.replace(/^\?/, '').replace(/^\//, '');
    if (!queryStr) {
      location.search = '/2026/frc';
    }
  });
</script>

<Container class="mt-2 d-flex align-items-center justify-content-center h-100">
  <Spinner />
</Container>
