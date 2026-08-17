<script>
	import favicon from '$lib/assets/favicon.svg';

	export let children;
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
</svelte:head>

<slot />
