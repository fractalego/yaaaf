const port = process.env.YAAF_API_PORT || 4000;
console.log(`Using backend port as YAAF_API_PORT=${port}`);

export const create_stream_url = `http://localhost:${port}/create_stream`;
export const get_utterances_url = `http://localhost:${port}/get_utterances`;
export const get_image_url = `http://localhost:${port}/get_image`;
export const get_artefact_url = `http://localhost:${port}/get_artefact`;

export const complete_tag = '<taskcompleted/>';
